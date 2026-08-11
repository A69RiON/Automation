let data={updated_at:null,deals:[]};
let activeTab="good";

const el=id=>document.getElementById(id);
const money=v=>v==null?null:new Intl.NumberFormat("en-AU",{style:"currency",currency:"AUD",maximumFractionDigits:2}).format(v);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

async function load(){
  try{
    const r=await fetch("data/deals.json",{cache:"no-store"});
    data=await r.json();
  }catch(e){ console.error(e); }
  setup();
  el("demoBanner").hidden=!data.demo;
  renderHealth();
  render();
}
function setup(){
  el("lastUpdated").textContent="Last updated: "+(data.updated_at?new Date(data.updated_at).toLocaleString("en-AU"):"unknown");
  const retailers=[...new Set(data.deals.map(d=>d.retailer))].sort();
  const cats=[...new Set(data.deals.map(d=>d.category))].sort();
  retailers.forEach(x=>el("retailer").insertAdjacentHTML("beforeend",`<option>${esc(x)}</option>`));
  cats.forEach(x=>el("category").insertAdjacentHTML("beforeend",`<option>${esc(x)}</option>`));
  document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{
    activeTab=b.dataset.tab;
    document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x===b));
    render();
  }));
  ["search","retailer","category","sort"].forEach(id=>el(id).addEventListener(id==="search"?"input":"change",render));
  el("closeDialog").addEventListener("click",()=>el("scoreDialog").close());
}

function renderHealth(){
  const hs=data.source_health||[];
  const healthy=hs.filter(h=>["ok","partial"].includes(h.status)).length;
  el("healthSummary").textContent=hs.length?`${healthy}/${hs.length} operational`:`No health data`;
  el("sourceHealth").innerHTML=hs.map(h=>`<div class="health-item">
    <div class="health-row"><span class="health-name">${esc(h.source)}</span><span class="health-${esc(h.status)}">${esc(h.status.replaceAll("_"," "))}</span></div>
    <div class="health-msg">${h.deals_found||0} fresh records · ${esc(h.message||"")}</div>
  </div>`).join("");
}

function currentDeals(){
  let ds=[...data.deals];
  if(activeTab==="good") ds=ds.filter(d=>d.good_deal===true);
  const q=el("search").value.toLowerCase().trim(), r=el("retailer").value, c=el("category").value;
  if(q) ds=ds.filter(d=>`${d.title} ${d.model||""} ${d.retailer}`.toLowerCase().includes(q));
  if(r) ds=ds.filter(d=>d.retailer===r);
  if(c) ds=ds.filter(d=>d.category===c);
  const s=el("sort").value;
  ds.sort((a,b)=>s==="discount"?(b.discount_percent??-1)-(a.discount_percent??-1):
    s==="priceLow"?(a.price??Infinity)-(b.price??Infinity):s==="priceHigh"?(b.price??-1)-(a.price??-1):
    s==="newest"?new Date(b.first_seen)-new Date(a.first_seen):b.deal_score-a.deal_score);
  return ds;
}
function render(){
  const all=data.deals, good=all.filter(d=>d.good_deal);
  const pcts=all.map(d=>d.discount_percent).filter(v=>v!=null);
  const best=pcts.length?Math.max(...pcts):0;
  el("metrics").innerHTML=`
    <div class="metric"><div class="label">Detected discounts</div><div class="value">${all.length}</div></div>
    <div class="metric"><div class="label">Good deals</div><div class="value">${good.length}</div></div>
    <div class="metric"><div class="label">Best discount</div><div class="value">${best.toFixed(0)}%</div></div>
    <div class="metric"><div class="label">Retailers scanned</div><div class="value">${new Set(all.map(d=>d.retailer)).size}</div></div>`;
  el("viewNote").textContent=activeTab==="good"
    ?"Ranked deals that pass the value-quality rules. Nothing is deleted; weaker promotions remain under All Discounts."
    :"Every detected promotion, including ordinary 10–20% sales and offers that may not beat historical street prices.";
  const ds=currentDeals();
  el("empty").hidden=ds.length>0;
  el("dealGrid").innerHTML=ds.map(card).join("");
  document.querySelectorAll("[data-score-id]").forEach(b=>b.addEventListener("click",()=>showScore(b.dataset.scoreId)));
}
function card(d){
  const cls=d.deal_score>=85?"score-high":"score-mid";
  const historical=d.historical_low?`Historical low: <strong>${money(d.historical_low)}</strong>`:"Historical low: collecting data";
  const market=d.market_average?`Market avg: <strong>${money(d.market_average)}</strong>`:"";
  const priceText=money(d.price)||"See deal";
  const wasText=money(d.was_price);
  const discountText=d.discount_percent!=null?`-${d.discount_percent.toFixed(0)}%`:"Promotion";
  const stale=d.last_seen && (Date.now()-new Date(d.last_seen).getTime()>36*3600*1000);
  return `<article class="deal-card ${stale?"stale":""}">
    <div class="card-head"><div class="title">${esc(d.title)}</div><div class="retailer">${esc(d.retailer)}</div></div>
    <div class="badges">
      <span class="badge ${cls}">Score ${d.deal_score}/100</span>
      <span class="badge">${esc(d.category)}</span>
      ${d.ozbargain_votes!=null?`<span class="badge">OzB +${d.ozbargain_votes}</span>`:""}
      ${d.suspected_inflated_rrp?`<span class="badge risk">RRP check</span>`:""}
    </div>
    <div class="price-row"><span class="price">${priceText}</span>${wasText?`<span class="was">${wasText}</span>`:""}<span class="discount">${discountText}</span></div>
    <div class="comp">${historical}<br>${market}</div>
    <div><div class="scorebar"><div class="scorefill" style="width:${Math.min(100,d.deal_score)}%"></div></div></div>
    <div class="actions">
      <button data-score-id="${esc(d.id)}">Why this score?</button>
      <a class="primary" href="${esc(d.url)}" target="_blank" rel="noopener">View deal</a>
    </div>
  </article>`;
}
function showScore(id){
  const d=data.deals.find(x=>x.id===id); if(!d)return;
  const b=d.score_breakdown||{};
  el("scoreDetails").innerHTML=`<h2>${esc(d.title)}</h2>
  <p class="explain">The advertised discount is always retained. The score separately estimates how attractive the deal is compared with history and competitors.</p>
  <div class="breakdown">
    ${Object.entries(b).map(([k,v])=>`<div class="break-row"><span>${esc(k.replaceAll("_"," "))}</span><strong>${v}</strong></div>`).join("")}
    <div class="break-row"><span>Total</span><strong>${d.deal_score}/100</strong></div>
  </div>
  ${d.suspected_inflated_rrp?`<p class="risk">⚠ Advertised RRP/was-price appears materially above observed market pricing. The discount is shown, but penalised in the Good Deals score.</p>`:""}`;
  el("scoreDialog").showModal();
}
load();
