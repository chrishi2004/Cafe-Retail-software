import type { Metadata } from "next";
import "../src/legacy/styles.css";
export const metadata: Metadata = {
  title: "Kalpvriksh Group",
  description: "Kalpvriksh Retail and Cafe operations",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
