import request from './request'

export interface PostListParams {
  page?: number
  page_size?: number
  /** 按公司名模糊匹配 */
  company_name?: string
  /** 在标题/正文/岗位里搜关键词 */
  keyword?: string
}

export function getPosts(params: PostListParams = {}) {
  return request.get('/community/posts', { params })
}

export function createPost(data: {
  title: string
  content: string
  company_name?: string
  position_name?: string
}) {
  return request.post('/community/posts', data)
}

export function getPost(id: number) {
  return request.get(`/community/posts/${id}`)
}

export function likePost(id: number) {
  return request.post(`/community/posts/${id}/like`)
}

// ---- 评论 ----
export function getComments(postId: number) {
  return request.get(`/community/posts/${postId}/comments`)
}

export function createComment(postId: number, content: string) {
  return request.post(`/community/posts/${postId}/comments`, { content })
}

export function deleteComment(commentId: number) {
  return request.delete(`/community/comments/${commentId}`)
}
