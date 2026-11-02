import request from './request'

export function getPracticeModes() {
  return request.get('/dict/practice-modes')
}

export function getPersonas() {
  return request.get('/dict/interviewer-personas')
}

export function getTechDirections() {
  return request.get('/dict/tech-directions')
}
