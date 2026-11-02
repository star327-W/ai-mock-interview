import request from './request'

export function uploadResume(file: File, isDefault = 0) {
  const fd = new FormData()
  fd.append('file', file)
  fd.append('is_default', String(isDefault))
  return request.post('/resumes', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    // 后端上传后要调大模型做结构化解析，可能十几秒；
    // 全局默认超时 15s 会把它掐断，这里单独放宽
    timeout: 60000
  })
}

export function listResumes() {
  return request.get('/resumes')
}

export function deleteResume(id: number) {
  return request.delete(`/resumes/${id}`)
}

/**
 * 简历详情：含 parsed_struct（结构化内容）和 projects。
 * 注意 parsed_struct 后端存的是**数据库里的 JSON 字符串**，用之前要先 JSON.parse。
 */
export function getResume(id: number) {
  return request.get(`/resumes/${id}`)
}

// 设为默认简历。
// 注意：后端的 is_default 是 FastAPI 查询参数（不是请求体），
// 必须走 params，放 body 里不会生效。
export function setDefaultResume(id: number) {
  return request.put(`/resumes/${id}`, null, { params: { is_default: 1 } })
}

export function createTargetPosition(data: any) {
  return request.post('/resumes/target-positions', data)
}

export function listTargetPositions() {
  return request.get('/resumes/target-positions')
}

export function deleteTargetPosition(id: number) {
  return request.delete(`/resumes/target-positions/${id}`)
}

export function getUserTechDirections() {
  return request.get('/resumes/tech-directions')
}

export function saveUserTechDirections(ids: number[]) {
  return request.put('/resumes/tech-directions', { tech_direction_ids: ids })
}
