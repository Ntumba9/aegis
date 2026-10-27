"""Webhook registration + a "send test event" action. Actual outbound
delivery for real events isn't wired to anything yet (there's no event
bus triggering it on e.g. task.created) — this gives orgs a working
signed-delivery mechanism and a way to verify their endpoint receives and
can verify the signature, which is the part most worth getting right and
testing.
"""
import json
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import CurrentUser, RequireRole
from app.db.session import get_pool
from app.schemas.webhooks import WebhookCreate, WebhookCreated, WebhookDeliveryOut, WebhookOut
from app.services import webhooks as webhook_service

router = APIRouter(prefix="/orgs/{org_id}/webhooks", tags=["webhooks"])


@router.post("", response_model=WebhookCreated, status_code=201)
async def create_webhook(
    org_id: UUID, body: WebhookCreate, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    signing_secret = secrets.token_urlsafe(32)
    row = await pool.fetchrow(
        "insert into webhooks (org_id, target_url, signing_secret, event_types, created_by) "
        "values ($1, $2, $3, $4, $5) "
        "returning id, org_id, target_url, event_types, is_active, created_at",
        org_id,
        body.target_url,
        signing_secret,
        body.event_types,
        user.id,
    )
    return WebhookCreated(signing_secret=signing_secret, **dict(row))


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(org_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))):
    pool = await get_pool()
    rows = await pool.fetch(
        "select id, org_id, target_url, event_types, is_active, created_at "
        "from webhooks where org_id = $1 order by created_at desc",
        org_id,
    )
    return [dict(r) for r in rows]


@router.delete("/{webhook_id}", status_code=204)
async def delete_webhook(
    org_id: UUID, webhook_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    result = await pool.execute(
        "update webhooks set is_active = false where id = $1 and org_id = $2", webhook_id, org_id
    )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Webhook not found")


@router.post("/{webhook_id}/test", response_model=WebhookDeliveryOut)
async def send_test_event(
    org_id: UUID, webhook_id: UUID, user: CurrentUser = Depends(RequireRole("admin"))
):
    pool = await get_pool()
    webhook = await pool.fetchrow(
        "select target_url, signing_secret from webhooks where id = $1 and org_id = $2 and is_active",
        webhook_id,
        org_id,
    )
    if webhook is None:
        raise HTTPException(status_code=404, detail="Webhook not found or inactive")

    delivery = await pool.fetchrow(
        "insert into webhook_deliveries (webhook_id, event_type, payload, status, attempt_count, last_attempted_at) "
        "values ($1, 'webhook.test', $2, 'pending', 1, now()) "
        "returning id, webhook_id, event_type, status, attempt_count, created_at",
        webhook_id,
        json.dumps({"event": "webhook.test", "org_id": str(org_id)}),
    )

    succeeded = await webhook_service.deliver(
        webhook["target_url"],
        webhook["signing_secret"],
        {"event": "webhook.test", "org_id": str(org_id)},
        max_retries=1,
    )
    await pool.execute(
        "update webhook_deliveries set status = $1 where id = $2",
        "delivered" if succeeded else "failed",
        delivery["id"],
    )
    return dict({**delivery, "status": "delivered" if succeeded else "failed"})
