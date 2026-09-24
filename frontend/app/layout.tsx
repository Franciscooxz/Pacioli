import type { Metadata } from "next";
import { Nunito_Sans } from "next/font/google";
import "./globals.css";

const sans = Nunito_Sans({
  subsets: ["latin"],
  weight: ["400", "600", "700", "800"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "Contaflow",
  description: "Automatizacion contable para firmas colombianas",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es" className={sans.variable}>
      <body>{children}</body>
    </html>
  );
}
