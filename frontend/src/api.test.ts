// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest'
import {api} from './api'

describe('API client authentication',()=>{
  afterEach(()=>{localStorage.clear();vi.restoreAllMocks()})
  it('adds the bearer token to protected requests',async()=>{
    localStorage.setItem('warehouse_token','signed-token')
    const fetchMock=vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({ok:true}),{status:200,headers:{'Content-Type':'application/json'}}))
    await api('/dashboard')
    expect(fetchMock).toHaveBeenCalledWith('/api/dashboard',expect.objectContaining({headers:expect.objectContaining({Authorization:'Bearer signed-token'})}))
  })
  it('surfaces API validation errors',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({detail:'Invalid request'}),{status:422,headers:{'Content-Type':'application/json'}}))
    await expect(api('/products')).rejects.toThrow('Invalid request')
  })
})
