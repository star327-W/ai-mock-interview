import request from './request'

export interface MembershipPlan {
  id: number
  code: string
  name: string
  price_fen: number
  duration_days: number
  interview_quota: number | null
  is_time_card: boolean
  is_first_charge: boolean
  purchasable: boolean
  features: { tag?: string; original_price_fen?: number; desc?: string }
}

export interface MembershipMe {
  membership: {
    plan_id: number | null
    plan_name: string | null
    status: number
    expire_at: string | null
    is_active: boolean
  }
  free_quota: { remain_count: number; total_granted: number }
  is_demo?: boolean
  first_charge_used: boolean
}

export interface OrderItem {
  id: number
  order_no: string
  plan_name: string
  amount_fen: number
  pay_type: string
  pay_status: number
  paid_at: string | null
  created_at: string | null
}

export function getMembershipMe(): Promise<MembershipMe> {
  return request.get('/membership/me')
}

export function getPlans(): Promise<MembershipPlan[]> {
  return request.get('/membership/plans')
}

export function createOrder(planId: number, payType = 'WECHAT') {
  return request.post(`/membership/orders?plan_id=${planId}&pay_type=${payType}`)
}

export function getOrders(): Promise<OrderItem[]> {
  return request.get('/membership/orders')
}
