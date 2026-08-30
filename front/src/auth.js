// 登录态：token + 用户名存 localStorage（退出时清掉；后续接口需要鉴权时在请求头带上 token）
const TOKEN_KEY = 'travelgen_token'
const USER_KEY = 'travelgen_username'

export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}
export function getUsername() {
  return localStorage.getItem(USER_KEY)
}
export function isLoggedIn() {
  return !!getToken()
}
export function setSession(token, username) {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, username)
}
export function logout() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
