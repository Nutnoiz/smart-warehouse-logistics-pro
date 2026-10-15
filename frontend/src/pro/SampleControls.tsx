import {useState} from 'react'
import {Database,Layers3,PackagePlus,Trash2} from 'lucide-react'
import {post} from '../api'
import {useAccount} from '../ProApp'
import {useResource} from './useResource'
import './samples.css'

type Profile='single'|'minimal'|'medium'|'large'
type SampleStatus={profile:Profile|null;demo_mode:boolean;counts:Record<string,number>;catalog_products:number}
const profiles:{id:Profile;label:string;description:string}[]=[
  {id:'single',label:'สร้าง 1 สินค้า Inbound',description:'1 HU ที่ Inbound · ทดลองทีละขั้น'},
  {id:'minimal',label:'สร้าง Minimal',description:'4 SKU · 12 HU · รถทำงาน 2 คัน'},
  {id:'medium',label:'สร้างแบบกลาง',description:'12 SKU · 46 HU · รถทำงาน 6 คัน'},
  {id:'large',label:'สร้างแบบเยอะ',description:'12 SKU · 178 HU · รถทำงาน 16 คัน'},
]
export function SampleControls({onChanged}:{onChanged:()=>void}){
  const account=useAccount();const resource=useResource<SampleStatus|null>('/pro/samples',null);const {data}=resource
  const [busy,setBusy]=useState('');const [error,setError]=useState('');const [message,setMessage]=useState('')
  if(!account.demo_mode||!account.permissions.includes('users'))return null
  async function change(profile?:Profile){
    if(busy)return;setBusy(profile||'clear');setError('');setMessage('')
    try{
      await post(profile?'/pro/samples':'/pro/samples/clear',profile?{profile}:{})
      await resource.reload();onChanged()
      setMessage(profile?`${profiles.find(p=>p.id===profile)?.label} เรียบร้อยแล้ว`:'ล้างเฉพาะธุรกรรมตัวอย่างแล้ว รายชื่อสินค้า ลูกค้า รถขนส่ง คนขับ และผังคลังยังอยู่ครบ')
    }catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  return <div className="sample-controls">
    <div className="sample-controls-title"><div><Database size={20}/></div><span><b>ชุดข้อมูลตัวอย่าง · ของตกแต่งบ้าน</b><small>ล้างเฉพาะธุรกรรม · คงรายชื่อสินค้า ลูกค้า รถขนส่ง คนขับ และผังคลัง</small></span>
      {data&&<em>{data.profile?`${data.profile.toUpperCase()} · ${data.counts.handling_units||0} HU · ${data.counts.products||0} SKU`:`ทะเบียนสินค้า ${data.catalog_products||0} SKU`}</em>}
    </div>
    <div className="sample-controls-actions">
      {profiles.map(p=><button key={p.id} className={`sample-create ${p.id==='medium'||p.id==='large'?'medium':''}`} title={p.description} disabled={Boolean(busy)} onClick={()=>void change(p.id)}>
        {p.id==='single'?<PackagePlus size={15}/>:p.id==='minimal'?<Database size={15}/>:<Layers3 size={15}/>}{busy===p.id?'กำลังสร้าง…':p.label}
      </button>)}
      <button className="sample-clear" disabled={Boolean(busy)||resource.loading||Boolean(resource.error)} onClick={()=>{if(window.confirm('ล้างรายการรับเข้า สต็อก การจัดส่ง และประวัติของชุดตัวอย่าง? รายชื่อสินค้า ลูกค้า รถ คนขับ ผังคลัง และข้อมูลทั่วไปจะยังอยู่'))void change()}}><Trash2 size={15}/>{busy==='clear'?'กำลังล้าง…':'ล้างข้อมูลตัวอย่าง'}</button>
    </div>
    <div className="sample-size-guide">{profiles.map(p=><span key={p.id}><b>{p.id==='single'?'ทีละขั้น':p.id==='large'?'เยอะ':p.id==='medium'?'กลาง':'Minimal'}</b> {p.description}</span>)}</div>
    {busy&&<div className="sample-message" role="status">กำลังจัดข้อมูลและประวัติ กรุณารอสักครู่…</div>}
    {(error||resource.error)&&<div className="sample-error" role="alert">{error||resource.error}</div>}
    {message&&<div className="sample-message" role="status">{message}</div>}
  </div>
}
