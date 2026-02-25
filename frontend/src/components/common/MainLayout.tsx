import { ReactNode } from 'react';
import Sidebar from '../Sidebar';
import Breadcrumb from './Breadcrumb';

interface MainLayoutProps {
  children: ReactNode;
}

export default function MainLayout({ children }: MainLayoutProps) {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-wrapper">
        <div className="content-wrapper">
          <Breadcrumb />
          <main className="main-content">
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
