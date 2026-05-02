import { Public_Sans } from 'next/font/google';
import { APP_CONFIG_DEFAULTS } from '@/app-config';
import '@/styles/globals.css';

const publicSans = Public_Sans({
  variable: '--font-public-sans',
  subsets: ['latin'],
});

export const metadata = {
  title: APP_CONFIG_DEFAULTS.pageTitle,
  description: APP_CONFIG_DEFAULTS.pageDescription,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${publicSans.variable} scroll-smooth font-sans antialiased`}>
      <body className="overflow-x-hidden">{children}</body>
    </html>
  );
}