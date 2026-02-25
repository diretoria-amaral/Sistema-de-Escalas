import { useState, useEffect } from 'react';
import { apiClient } from '../services/client';

interface ModeStatus {
  intermittent_mode_active: boolean;
  work_regime_mode: string;
  alert_message: string | null;
}

export default function IntermittentModeAlert() {
  const [status, setStatus] = useState<ModeStatus | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const response = await apiClient.get('/compliance/intermittent-mode-status');
      setStatus(response.data);
    } catch (error) {
      console.error('Error loading intermittent mode status:', error);
    }
  };

  if (!status || !status.intermittent_mode_active || !status.alert_message) {
    return null;
  }

  return (
    <div style={{ 
      backgroundColor: '#fef3c7',
      borderBottom: '1px solid #f59e0b',
      padding: '8px 20px',
      fontSize: '13px',
      color: '#92400e',
      display: 'flex',
      alignItems: 'center',
      gap: '8px'
    }}>
      <span style={{ fontSize: '16px' }}>&#9888;</span>
      <span>{status.alert_message}</span>
    </div>
  );
}
