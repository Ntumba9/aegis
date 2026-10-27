import "./globals.css";

export const metadata = {
  title: "AEGIS — Build. Break. Defend.",
  description: "Open-source API security training platform and OWASP API Top 10 laboratory.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-charcoal text-slate-100 min-h-screen antialiased">{children}</body>
    </html>
  );
}
