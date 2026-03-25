import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "WasteIQ — AI Material Waste Prediction",
  description: "Predict construction material waste before you order.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  );
}
