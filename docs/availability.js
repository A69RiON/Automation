import {createClient} from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
const c=window.MARKETPLACE_CONFIG,s=createClient(c.SUPABASE_URL,c.SUPABASE_PUBLISHABLE_KEY),r=document.getElementById("availabilityList");
const f=d=>d?new Intl.DateTimeFormat("en-AU",{day:"numeric",month:"short",year:"numeric"}).format(new Date(d+"T00:00:00")):"No date found";
const {data,error}=await s.rpc("offering_availability_summary");
r.innerHTML=error?`<div class="result error">${error.message}</div>`:(data||[]).map(x=>`<article class="availability-row"><div><strong>${x.title}</strong><div class="meta">${x.platform||"Digital"}</div></div><div class="availability-state ${x.status_label}">${x.available_today>0?`<strong>Available now</strong><span>${x.available_today} of ${x.capacity} slot(s) available</span>`:`<strong>Booked</strong><span>Next available: ${f(x.next_available_date)}</span>`}</div></article>`).join("")||"<p>No active rentals.</p>";
