// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest'
import {api,post} from '../api'

describe('Operational request safety',()=>{
  afterEach(()=>{localStorage.clear();vi.restoreAllMocks()})
  it('shares a pending identical mutation instead of writing twice',async()=>{
    let complete!:(value:Response)=>void
    const fetchMock=vi.spyOn(globalThis,'fetch').mockImplementation(()=>new Promise(resolve=>{complete=resolve}))
    const first=post('/pro/counts',{inventory_id:1,counted_quantity:90,reason:'Cycle count'})
    const second=post('/pro/counts',{inventory_id:1,counted_quantity:90,reason:'Cycle count'})
    expect(fetchMock).toHaveBeenCalledTimes(1)
    complete(new Response(JSON.stringify({id:42})))
    expect(await first).toEqual({id:42});expect(await second).toEqual({id:42})
  })
  it('renders structured validation errors as useful field messages',async()=>{
    vi.spyOn(globalThis,'fetch').mockResolvedValue(new Response(JSON.stringify({detail:[{loc:['body','quantity'],msg:'Input should be greater than 0'}]}),{status:422}))
    await expect(api('/inbound/receive')).rejects.toThrow('quantity: Input should be greater than 0')
  })
})
