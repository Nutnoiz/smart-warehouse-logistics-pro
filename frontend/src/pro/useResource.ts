import {useCallback, useEffect, useRef, useState} from 'react'
import {api} from '../api'

export function useResource<T>(path:string, initial:T, interval=0){
  const [data,setData]=useState<T>(initial)
  const [loading,setLoading]=useState(true)
  const [error,setError]=useState('')
  const [updated,setUpdated]=useState<Date|null>(null)
  const active=useRef(true)
  const sequence=useRef(0)
  const reload=useCallback(async()=>{
    const id=++sequence.current
    try{const value=await api<T>(path);if(active.current&&id===sequence.current){setData(value);setError('');setUpdated(new Date())}}
    catch(e){if(active.current&&id===sequence.current)setError((e as Error).message)}
    finally{if(active.current&&id===sequence.current)setLoading(false)}
  },[path])
  useEffect(()=>{active.current=true;setLoading(true);void reload();const timer=interval?setInterval(()=>{if(!document.hidden)void reload()},interval):undefined;return()=>{active.current=false;++sequence.current;if(timer)clearInterval(timer)}},[reload,interval])
  return {data,loading,error,updated,reload}
}
