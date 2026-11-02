import request from './request'

export function getHistory() {
  return request.get('/growth/history')
}

export function getTrend() {
  return request.get('/growth/trend')
}

export function getSummary() {
  return request.get('/growth/summary')
}

export interface LearningTaskItem {
  id: number
  title: string
  content: string | null
  task_date: string | null
  is_done: boolean
}

export interface LearningPlanItem {
  id: number
  title: string
  target: string | null
  strengths_text: string | null
  weaknesses_text: string | null
  start_date: string | null
  end_date: string | null
  status: number
  progress: number
  task_total: number
  task_done: number
  tasks: LearningTaskItem[]
}

export function getLearningPlans(): Promise<LearningPlanItem[]> {
  return request.get('/growth/learning-plans')
}

export interface ToggleTaskResult {
  task_id: number
  is_done: boolean
  task_done: number
  task_total: number
  progress: number
  plan_status: number
}

export function toggleLearningTask(taskId: number): Promise<ToggleTaskResult> {
  return request.post(`/growth/learning-plans/tasks/${taskId}/toggle`)
}
