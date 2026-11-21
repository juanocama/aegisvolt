import React,{useEffect,useState} from "react";
import {createRoot} from "react-dom/client";
import {Environment,environment,gql} from "./graphql";
import "./styles.css";

type Connector={id:string,type:string,status:string,power_kw:number};
type Station={id:string,name:string,status:string,connectors:Connector[]};
type Saga={id:string,correlation_id:string,state:string,reservation_status:string,charge_status:string,activation_status:string,error?:string};
type Flag={name:string,enabled:boolean};

function App(){
 const [selectedEnvironment,setSelectedEnvironment]=useState<Environment>(environment);
 const [stations,setStations]=useState<Station[]>([]);
 const [sagas,setSagas]=useState<Saga[]>([]);
 const [flags,setFlags]=useState<Flag[]>([]);
 const [wallet,setWallet]=useState({balance:0,currency:"USD"});
 const [selected,setSelected]=useState("st-1");
 const [fault,setFault]=useState(false);
 const [message,setMessage]=useState("");

 async function load(){
  try{
   const d=await gql<{stations:Station[];wallet:{id:string,balance:number,currency:string};sagas:Saga[];flags:Flag[]}>(selectedEnvironment,`
    query { stations { id name status connectors { id type status power_kw } }
      wallet(walletId:"wallet-1"){id balance currency}
      sagas{id correlation_id state reservation_status charge_status activation_status error}
      flags{name enabled}
    }`);
   setStations(d.stations);setWallet(d.wallet);setSagas(d.sagas);setFlags(d.flags);
  }catch(e){setMessage(String(e));}
 }
 useEffect(()=>{load();const timer=window.setInterval(load,3000);return()=>clearInterval(timer)},[selectedEnvironment]);

 async function reserve(){
  setMessage("Starting SAGA...");
  const d=await gql<{reserveAndActivateCharge:{success:boolean,state:string,message:string,sagaId:string,correlationId:string}}>(selectedEnvironment,`
    mutation($fault:Boolean!){ reserveAndActivateCharge(walletId:"wallet-1",stationId:$station,connectorId:"c-1",amount:25.0,idempotencyKey:$key,chargeFault:$fault){success state message sagaId correlationId}}`,
    {fault,station:selected,key:crypto.randomUUID()});
  const r=d.reserveAndActivateCharge;
  setMessage(`${r.state}: ${r.message||"Charge flow updated"} (SAGA ${r.sagaId.slice(0,18)})`);
  await load();
 }
 async function retry(id:string){
  await gql(selectedEnvironment,`mutation($id:String!){retryCompensation(sagaId:$id){id state}}`,{id});await load();
 }
 return <main>
  <header><div><strong>AegisVolt</strong><nav className="environment-switch" aria-label="Environment">{(["dev","test","prod"] as Environment[]).map(env=><button key={env} className={selectedEnvironment===env?"active":""} onClick={()=>setSelectedEnvironment(env)}>{env}</button>)}</nav></div><div>Wallet <b>${wallet.balance.toFixed(2)} {wallet.currency}</b></div></header>
  <section className="grid">
   <article><h2>Stations</h2>{stations.map(s=><button className={selected===s.id?"station selected":"station"} key={s.id} onClick={()=>setSelected(s.id)}>
    <b>{s.name}</b><small>{s.status}</small>{s.connectors.map(c=><span key={c.id}>{c.id} · {c.type} · {c.power_kw} kW · {c.status}</span>)}
   </button>)}</article>
   <article><h2>Reserve & activate</h2><label><input type="checkbox" checked={fault} onChange={e=>setFault(e.target.checked)}/> Simulate charger fault</label>
    <button className="primary" onClick={reserve}>Reserve / activate charge</button><p role="status">{message}</p></article>
   <article><h2>Feature flags</h2>{flags.map(f=><div className="flag" key={f.name}><span>{f.name}</span><b className={f.enabled?"on":"off"}>{f.enabled?"ON":"OFF"}</b></div>)}</article>
  </section>
  <section><h2>SAGA history</h2><div className="table"><table><thead><tr><th>ID</th><th>Correlation</th><th>State</th><th>Reservation</th><th>Charge</th><th>Activation</th><th></th></tr></thead><tbody>{sagas.map(s=><tr key={s.id}><td>{s.id}</td><td>{s.correlation_id}</td><td>{s.state}</td><td>{s.reservation_status}</td><td>{s.charge_status}</td><td>{s.activation_status}</td><td>{["COMPENSATION_FAILED","FAILED"].includes(s.state)&&<button onClick={()=>retry(s.id)}>Retry compensation</button>}</td></tr>)}</tbody></table></div></section>
 </main>
}
createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
