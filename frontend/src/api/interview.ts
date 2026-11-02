import request from './request'

export function createSession(data: any) {
  return request.post('/interview/sessions', data)
}

export function startSession(id: number) {
  return request.post(`/interview/sessions/${id}/start`)
}

export function askNext(id: number, parent_id?: number) {
  return request.post(`/interview/sessions/${id}/ask`, null, {
    params: parent_id !== undefined ? { parent_id } : {}
  })
}

/**
 * 流式出题(SSE):题目文字逐块回调给 onDelta,像打字一样显示。
 * axios 不支持流式读取,所以这里直接用 fetch + ReadableStream。
 * 返回完整题目文本。
 */
export async function askNextStream(
  id: number,
  onDelta: (delta: string) => void,
  onDone?: (meta: {
    question_id?: number
    seq?: number
    /** 题目类型；「收尾环节」表示这是面试官的最后一段话，面试到此结束 */
    intent?: string
  }) => void,
): Promise<string> {
  const token = localStorage.getItem('mock_interview_token')
  const base = (import.meta as any).env?.VITE_API_BASE_URL || '/api'

  const resp = await fetch(`${base}/interview/sessions/${id}/ask-stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!resp.ok || !resp.body) {
    throw new Error(`流式请求失败: HTTP ${resp.status}`)
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let full = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    // SSE 事件以空行分隔
    const parts = buffer.split('\n\n')
    buffer = parts.pop() || ''
    for (const part of parts) {
      const line = part.trim()
      if (!line.startsWith('data:')) continue
      let obj: any
      try {
        obj = JSON.parse(line.slice(5).trim())
      } catch {
        continue
      }
      if (obj.delta) {
        full += obj.delta
        onDelta(obj.delta)
      } else if (obj.done) {
        onDone?.({ question_id: obj.question_id, seq: obj.seq, intent: obj.intent })
      } else if (obj.error) {
        throw new Error(obj.error)
      }
    }
  }
  return full
}

export function submitAnswer(id: number, payload: { question_id: number; answer_text: string; duration_sec?: number }) {
  return request.post(`/interview/sessions/${id}/answer`, payload)
}

export function endSession(id: number, reason?: string) {
  return request.post(`/interview/sessions/${id}/end`, null, {
    params: reason ? { reason } : {}
  })
}

export function getSessionDetail(id: number) {
  return request.get(`/interview/sessions/${id}`)
}

/** 我的所有面试会话（用来找出「还没结束的那一场」，让用户可以回去继续） */
export function listSessions() {
  return request.get('/interview/sessions')
}

/**
 * 面试页心跳：告诉后端"人还在页面上"。
 * 心跳断掉超过 10 分钟，这场面试会被后端自动结束。
 */
export function heartbeat(id: number) {
  return request.post(`/interview/sessions/${id}/heartbeat`)
}

export function deleteSession(id: number) {
  return request.delete(`/interview/sessions/${id}`)
}
