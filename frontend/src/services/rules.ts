import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

export type RuleType = 'LABOR' | 'SYSTEM' | 'OPERATIONAL' | 'CALCULATION';
export type RigidityLevel = 'MANDATORY' | 'DESIRABLE' | 'FLEXIBLE';

export interface SectorRule {
  id: number;
  setor_id: number | null;
  is_global: boolean;
  tipo_regra: RuleType;
  nivel_rigidez: RigidityLevel;
  codigo_regra: string;
  title?: string | null;
  pergunta: string;
  resposta: string;
  prioridade: number;
  regra_ativa: boolean;
  validade_inicio?: string | null;
  validade_fim?: string | null;
  metadados_json?: Record<string, any> | null;
  created_at: string;
  updated_at?: string;
}

export interface SectorRuleCreate {
  setor_id?: number | null;
  is_global?: boolean;
  tipo_regra: RuleType;
  nivel_rigidez: RigidityLevel;
  title: string;
  pergunta: string;
  resposta: string;
  prioridade?: number;
  regra_ativa?: boolean;
  validade_inicio?: string;
  validade_fim?: string;
}

export interface SectorRuleUpdate {
  title?: string;
  pergunta?: string;
  resposta?: string;
  nivel_rigidez?: RigidityLevel;
  prioridade?: number;
  regra_ativa?: boolean;
  validade_inicio?: string;
  validade_fim?: string;
}

export interface RigidityGroup {
  MANDATORY?: SectorRule[];
  DESIRABLE?: SectorRule[];
  FLEXIBLE?: SectorRule[];
}

export interface GroupedRulesResponse {
  labor: RigidityGroup;
  system: RigidityGroup;
  operational: RigidityGroup;
  calculation: RigidityGroup;
}

export interface ReorderRequest {
  rule_ids: number[];
}

export const sectorRulesApi = {
  list: (sectorId?: number) => 
    api.get<SectorRule[]>('/sector-rules', { params: sectorId ? { setor_id: sectorId } : {} }),
  
  listGlobal: (type: RuleType) =>
    api.get<SectorRule[]>('/sector-rules/global', { params: { tipo_regra: type } }),
  
  getGrouped: (sectorId: number) =>
    api.get<GroupedRulesResponse>(`/rule-engine/rules/grouped/${sectorId}`),
  
  get: (id: number) => 
    api.get<SectorRule>(`/sector-rules/${id}`),
  
  create: (data: SectorRuleCreate) => 
    api.post<SectorRule>('/sector-rules', data),
  
  update: (id: number, data: SectorRuleUpdate) => 
    api.put<SectorRule>(`/sector-rules/${id}`, data),
  
  delete: (id: number) => 
    api.delete(`/sector-rules/${id}`),
  
  toggle: (id: number) =>
    api.post<SectorRule>(`/sector-rules/${id}/toggle`),
  
  clone: (id: number, newTitle: string) =>
    api.post<SectorRule>(`/sector-rules/${id}/clone`, { new_title: newTitle }),
  
  reorder: (sectorId: number, type: RuleType, ruleIds: number[]) =>
    api.post(`/sector-rules/reorder/${sectorId}/${type}`, { rule_ids: ruleIds }),
  
  reorderGlobal: (type: RuleType, ruleIds: number[]) =>
    api.post(`/sector-rules/reorder-global/${type}`, { rule_ids: ruleIds }),
  
  getLaborConstraints: (sectorId: number) =>
    api.get(`/rule-engine/labor-constraints/${sectorId}`),
  
  checkConsistency: (sectorId: number, type: RuleType) =>
    api.get(`/rule-engine/consistency/${sectorId}/${type}`),
};

export default sectorRulesApi;
