import request from './request'

export function getReport(sessionId: number) {
  return request.get(`/evaluation/reports/${sessionId}`)
}

export function getReviews(sessionId: number) {
  return request.get(`/evaluation/reports/${sessionId}/reviews`)
}
