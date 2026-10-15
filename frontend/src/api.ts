const API=import.meta.env.VITE_API_URL || '/api'
export async function api<T>(path:string, init?:RequestInit):Promise<T>{
  const token=localStorage.getItem('warehouse_token')
  const response=await fetch(`${API}${path}`,{...init,headers:{'Content-Type':'application/json',...(token?{'Authorization':`Bearer ${token}`}:{ }),...init?.headers}})
  if(response.status===401&&token){localStorage.removeItem('warehouse_token');window.location.reload();throw new Error('Session expired')}
  if(!response.ok){const detail=await response.json().catch(()=>({detail:'เชื่อมต่อระบบไม่สำเร็จ'}));throw new Error(errorMessage(detail.detail))}
  return response.json()
}
const pendingPosts=new Map<string,Promise<unknown>>()
export function post<T>(path:string,data:unknown):Promise<T>{const body=JSON.stringify(data);const key=path+body;const pending=pendingPosts.get(key);if(pending)return pending as Promise<T>;const request=api<T>(path,{method:'POST',body}).finally(()=>pendingPosts.delete(key));pendingPosts.set(key,request);return request}
function errorMessage(detail:unknown):string{if(typeof detail==='string')return detail;if(Array.isArray(detail))return detail.map(e=>`${e.loc?.slice(1).join('.')||'ข้อมูล'}: ${e.msg||'ไม่ถูกต้อง'}`).join(' · ');return 'ไม่สามารถทำรายการได้'}
export async function upload<T>(path:string,data:FormData):Promise<T>{const token=localStorage.getItem('warehouse_token');const response=await fetch(`${API}${path}`,{method:'POST',body:data,headers:token?{'Authorization':`Bearer ${token}`}:{}});if(response.status===401&&token){localStorage.removeItem('warehouse_token');window.location.reload();throw new Error('Session expired')}if(!response.ok){const detail=await response.json().catch(()=>({detail:'Upload failed'}));throw new Error(detail.detail||'Upload failed')}return response.json()}
