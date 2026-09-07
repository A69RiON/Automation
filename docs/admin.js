import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.4/+esm";
const cfg=window.MARKETPLACE_CONFIG;
const supabase=createClient(cfg.SUPABASE_URL,cfg.SUPABASE_PUBLISHABLE_KEY);
const $=id=>document.getElementById(id);
let offerings=[],bookings=[],editingId=null;

async function isAdmin(){
  const {data:{user}}=await supabase.auth.getUser();
  if(!user)return false;
  const {data}=await supabase.from("admin_users").select("user_id").eq("user_id",user.id).maybeSingle();
  return !!data;
}
async function boot(){
  if(await isAdmin()){showAdmin();await refreshAll();}
}
$("loginBtn").addEventListener("click",async()=>{
  const email=$("username").value.trim()+cfg.ADMIN_EMAIL_SUFFIX;
  const {error}=await supabase.auth.signInWithPassword({email,password:$("password").value});
  if(error){$("loginMsg").textContent=error.message;$("loginMsg").className="result error";return;}
  if(!(await isAdmin())){
    await supabase.auth.signOut();
    $("loginMsg").textContent="This account is not authorised as an administrator.";
    $("loginMsg").className="result error";return;
  }
  showAdmin();await refreshAll();
});
$("logoutBtn").addEventListener("click",async()=>{await supabase.auth.signOut();location.reload();});
function showAdmin(){$("loginPanel").hidden=true;$("adminPanel").hidden=false;$("logoutBtn").hidden=false;}

async function refreshAll(){
  const [b,o,s]=await Promise.all([
    supabase.from("bookings").select("*,offerings(title)").order("created_at",{ascending:false}),
    supabase.from("offerings").select("*").eq("archived",false).order("created_at",{ascending:false}),
    supabase.from("marketplace_settings").select("*").limit(1).maybeSingle()
  ]);
  bookings=b.data||[];offerings=o.data||[];
  renderMetrics();renderBookings();renderOfferings();
  if(s.data){$("siteName").value=s.data.site_name||"";$("supportEmail").value=s.data.support_email||"";}
}

function renderMetrics(){
  const active=bookings.filter(b=>["pending","sent","confirmed","in_progress"].includes(b.status)).length;
  $("adminMetrics").innerHTML=`
    <div class="metric"><div class="v">${bookings.length}</div><div class="l">Total bookings</div></div>
    <div class="metric"><div class="v">${active}</div><div class="l">Active bookings</div></div>
    <div class="metric"><div class="v">${offerings.filter(o=>o.active).length}</div><div class="l">Active offerings</div></div>
    <div class="metric"><div class="v">AUD</div><div class="l">Currency</div></div>`;
}

function renderBookings(){
  $("ordersTable").innerHTML=`<table class="table"><thead><tr><th>Booking</th><th>Customer</th><th>Offering</th><th>Dates</th><th>Total</th><th>Status</th></tr></thead><tbody>${
    bookings.map(b=>`<tr>
      <td>${esc(b.booking_number)}</td>
      <td>${esc(b.customer_name)}<br><span class="meta">${esc(b.customer_email)}</span></td>
      <td>${esc(b.offerings?.title||"Removed offering")}</td>
      <td>${b.start_date||"—"} → ${b.end_date||"—"}</td>
      <td>A$${Number(b.total_amount||0).toFixed(2)}</td>
      <td>
        <select class="status-select" data-id="${b.id}">
          ${["pending","sent","completed","cancelled"].map(s=>`<option value="${s}" ${b.status===s?"selected":""}>${labelStatus(s)}</option>`).join("")}
        </select>
        <button class="button delete-booking" data-id="${b.id}">Delete</button>
      </td>
    </tr>`).join("")
  }</tbody></table>`;

  document.querySelectorAll(".status-select").forEach(x=>x.addEventListener("change",async()=>{
    const {error}=await supabase.from("bookings").update({status:x.value}).eq("id",x.dataset.id);
    if(error)alert(error.message);
    await refreshAll();
  }));

  document.querySelectorAll(".delete-booking").forEach(x=>x.addEventListener("click",async()=>{
    if(!confirm("Permanently delete this booking? Normally use Cancelled so the booking history is retained."))return;
    const {error}=await supabase.from("bookings").delete().eq("id",x.dataset.id);
    if(error)alert(error.message);
    await refreshAll();
  }));
}

function renderOfferings(){
  $("offeringsList").innerHTML=offerings.map(o=>`
    <div class="offer-row">
      <div>
        <strong>${esc(o.title)}</strong>
        <div class="meta">${esc(o.platform||"")} • ${o.offering_type} • capacity ${o.capacity}</div>
        <div class="meta">${o.offering_type==="digital_rental"
          ? `A$${Number(o.daily_rate||0).toFixed(2)}/day • A$${Number(o.weekly_rate||0).toFixed(2)}/week`
          : `A$${Number(o.base_price||0).toFixed(2)}`}</div>
        <div class="meta">${o.active?"Enabled":"Disabled"}</div>
      </div>
      <div class="offer-actions">
        <button class="button edit-offer" data-id="${o.id}">Edit</button>
        <button class="button toggle-offer" data-id="${o.id}" data-active="${o.active}">${o.active?"Disable":"Enable"}</button>
        <button class="button remove-offer" data-id="${o.id}">Remove</button>
      </div>
    </div>`).join("");

  document.querySelectorAll(".edit-offer").forEach(b=>b.addEventListener("click",()=>startEdit(b.dataset.id)));

  document.querySelectorAll(".toggle-offer").forEach(b=>b.addEventListener("click",async()=>{
    const {error}=await supabase.from("offerings").update({active:b.dataset.active!=="true"}).eq("id",b.dataset.id);
    if(error)alert(error.message);
    await refreshAll();
  }));

  document.querySelectorAll(".remove-offer").forEach(b=>b.addEventListener("click",async()=>{
    const o=offerings.find(x=>x.id===b.dataset.id);
    if(!confirm(`Remove "${o?.title||"this offering"}" from the marketplace?\n\nExisting bookings will be preserved. The listing will be archived and hidden.`))return;
    const {error}=await supabase.from("offerings").update({archived:true,active:false}).eq("id",b.dataset.id);
    if(error)alert(error.message);
    resetOfferForm();
    await refreshAll();
  }));
}

function startEdit(id){
  const o=offerings.find(x=>x.id===id); if(!o)return;
  editingId=id;
  $("offerTitle").value=o.title||"";
  $("offerType").value=o.offering_type||"digital_rental";
  $("offerPlatform").value=o.platform||"";
  $("offerDescription").value=o.description||"";
  $("offerDaily").value=o.daily_rate??0;
  $("offerWeekly").value=o.weekly_rate??0;
  $("offerCapacity").value=o.capacity??1;
  $("offerMaxDays").value=o.max_rental_days??14;
  $("offerImage").value=o.image_url||"";
  $("addOfferingBtn").textContent="Save changes";
  $("offerMsg").textContent=`Editing: ${o.title}`;
  $("offerMsg").className="result";
  $("offerTitle").scrollIntoView({behavior:"smooth",block:"center"});
}

function resetOfferForm(){
  editingId=null;
  ["offerTitle","offerPlatform","offerDescription","offerDaily","offerWeekly","offerImage"].forEach(id=>$(id).value="");
  $("offerCapacity").value=1;
  $("offerMaxDays").value=14;
  $("offerType").value="digital_rental";
  $("addOfferingBtn").textContent="Publish offering";
}

$("addOfferingBtn").addEventListener("click",async()=>{
  const payload={
    title:$("offerTitle").value.trim(),
    offering_type:$("offerType").value,
    platform:$("offerPlatform").value.trim(),
    description:$("offerDescription").value.trim(),
    daily_rate:Number($("offerDaily").value||0),
    weekly_rate:Number($("offerWeekly").value||0),
    base_price:Number($("offerDaily").value||0),
    capacity:Number($("offerCapacity").value||1),
    max_rental_days:Number($("offerMaxDays").value||14),
    image_url:$("offerImage").value.trim()||null,
    currency:"AUD",market:"AU"
  };
  if(!payload.title){
    $("offerMsg").textContent="Title is required.";
    $("offerMsg").className="result error";return;
  }

  let error;
  if(editingId){
    ({error}=await supabase.from("offerings").update(payload).eq("id",editingId));
  }else{
    ({error}=await supabase.from("offerings").insert({...payload,active:true,archived:false}));
  }

  $("offerMsg").textContent=error?error.message:(editingId?"Offering updated.":"Offering published.");
  $("offerMsg").className=error?"result error":"result success";
  if(!error){resetOfferForm();await refreshAll();}
});

$("saveSettingsBtn").addEventListener("click",async()=>{
  const {data}=await supabase.from("marketplace_settings").select("id").limit(1).maybeSingle();
  const payload={site_name:$("siteName").value.trim(),support_email:$("supportEmail").value.trim(),currency:"AUD",market:"AU"};
  const q=data?.id?supabase.from("marketplace_settings").update(payload).eq("id",data.id):supabase.from("marketplace_settings").insert(payload);
  const {error}=await q;
  $("settingsMsg").textContent=error?error.message:"Settings saved.";
  $("settingsMsg").className=error?"result error":"result success";
});

document.querySelectorAll(".tab").forEach(b=>b.addEventListener("click",()=>{
  document.querySelectorAll(".tab").forEach(x=>x.classList.toggle("active",x===b));
  ["orders","offerings","settings"].forEach(t=>$(t+"Tab").hidden=b.dataset.tab!==t);
}));

$("refreshBtn").addEventListener("click",refreshAll);
function labelStatus(s){return ({pending:"Pending",sent:"Sent / Active",completed:"Completed",cancelled:"Cancelled"}[s]||s);}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));}
boot();
