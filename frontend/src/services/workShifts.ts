import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
});

export type ShiftTimeConstraint = 'MANDATORY' | 'FLEXIBLE';

export interface WorkShiftDayRule {
  id?: number;
  weekday: number;
  start_time: string | null;
  break_out_time: string | null;
  break_in_time: string | null;
  end_time: string | null;
  start_constraint: ShiftTimeConstraint;
  end_constraint: ShiftTimeConstraint;
}

export interface WorkShift {
  id: number;
  sector_id: number;
  name: string;
  is_active: boolean;
  day_rules: WorkShiftDayRule[];
}

export interface WorkShiftCreate {
  sector_id: number;
  name: string;
  days: WorkShiftDayRule[];
}

export const workShiftsApi = {
  list: (sectorId: number, includeInactive: boolean = false) =>
    api.get<WorkShift[]>(`/work-shifts`, { params: { sector_id: sectorId, include_inactive: includeInactive } }),
  get: (id: number) => api.get<WorkShift>(`/work-shifts/${id}`),
  create: (data: WorkShiftCreate) => api.post<WorkShift>(`/work-shifts`, data),
  update: (id: number, data: Partial<WorkShiftCreate> & { is_active?: boolean }) =>
    api.put<WorkShift>(`/work-shifts/${id}`, data),
  delete: (id: number) => api.delete(`/work-shifts/${id}`),
};
