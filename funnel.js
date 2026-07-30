async function sendSnapshotToBackend(answers, name, phone) {
    try {
        const response = await fetch("http://127.0.0.1:8000/snapshot", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
           body: JSON.stringify({
                name: name,
                phone: phone,
                answers: answers
            })
        });

        const data = await response.json();
        console.log("Backend replied:", data);

    } catch (err) {
        console.error("Backend error:", err);
    }
}
(() => {
"use strict";
const A="nourisherAssessment", P="nourisherApplication";
const labels={recovery:"Recovery",metabolic:"Energy & Metabolic Rhythm",nutrition:"Nutrition & Cravings",behaviour:"Consistency",confidence:"Confidence & Self-trust"};
const descriptions={
recovery:"How supported your sleep, morning freshness and stress load currently feel.",
metabolic:"How steady your energy and physical wellbeing feel across the day.",
nutrition:"How manageable and predictable your cravings currently feel.",
behaviour:"How consistently you can follow through without repeatedly restarting.",
confidence:"How connected, capable and in control you currently feel."
};
const profiles={
belly:["You notice the biggest changes around your belly area.","This can feel especially frustrating in midlife. Your wider pattern—sleep, stress, energy, cravings and consistency—matters more than any one body area."],
overall:["You are noticing more general weight or body-composition changes.","Rather than treating this as one isolated issue, your snapshot looks at the habits and recovery patterns influencing the bigger picture."],
hips:["You notice the biggest changes around your hips or thighs.","Where the body changes is personal. The useful focus is sustainable nourishment, strength, recovery and metabolic health—not spot reduction."],
off:['More than one symptom may be contributing to the sense that you feel “off.”',"That feeling is valid. Looking at the whole picture can be more useful than chasing one symptom at a time."]
};
const feelingScore={"not-self":36,"out-control":28,frustrated:45,stuck:40,"starting-over":32};
const save=(k,v)=>localStorage.setItem(k,JSON.stringify(v));
const load=k=>{try{return JSON.parse(localStorage.getItem(k)||"{}")}catch{return{}}};
const scale=v=>({1:25,2:50,3:72,4:92}[Number(v)]||50);
const avg=a=>Math.round(a.reduce((x,y)=>x+y,0)/a.length);
function calculate(d){
 const wake=scale(d.wake),energy=scale(d.energy),cravings=scale(d.cravings),sleep=scale(d.sleep),stress=scale(d.stress),consistency=scale(d.consistency),confidence=feelingScore[d.feeling]||40;
 const dimensions={recovery:avg([wake,sleep,stress]),metabolic:avg([wake,energy]),nutrition:cravings,behaviour:consistency,confidence};
 const total=Math.round(dimensions.recovery*.28+dimensions.metabolic*.22+dimensions.nutrition*.18+dimensions.behaviour*.18+dimensions.confidence*.14);
 const ordered=Object.entries(dimensions).sort((a,b)=>a[1]-b[1]);
 return {answers:d,dimensions,total,opportunity:ordered[0][0],strength:ordered.at(-1)[0],bodyProfile:d.body,feeling:d.feeling,createdAt:new Date().toISOString()};
}
const intro=document.querySelector("[data-snapshot-intro]"), assessment=document.querySelector("[data-snapshot-assessment]");
document.querySelector("[data-start-snapshot]")?.addEventListener("click",()=>{
     const nameInput = document.getElementById("name");
     

    const phoneInput = document.getElementById("phone");
    const iti = window.intlTelInput(phoneInput, {

    initialCountry: "in",

    preferredCountries: ["in", "us"],

    separateDialCode: true,

    nationalMode: true,

    strictMode: true

});
    const phone = iti.getNumber();
    if (!phoneInput.checkValidity()) {
        phoneInput.reportValidity();
        return;
    }
    if (!nameInput.value.trim()) {
        nameInput.reportValidity();
        return;
    }
    intro.hidden=true;
 assessment.hidden=false;
 requestAnimationFrame(()=>{
  assessment.classList.add("active");
  const header=document.querySelector(".site-header");
  const offset=(header?.offsetHeight||78)+16;
  const targetTop=assessment.getBoundingClientRect().top+window.scrollY-offset;
  window.scrollTo({top:Math.max(0,targetTop),behavior:"smooth"});
 });
});
const form=document.querySelector("[data-assessment-form]");
if(form){
 const qs=[...form.querySelectorAll("[data-question]")], fill=document.querySelector("[data-progress-fill]"),txt=document.querySelector("[data-progress-text]"),pct=document.querySelector("[data-progress-percent]"),back=document.querySelector("[data-back]"); let current=0;
 const show=i=>{
  qs.forEach((q,j)=>q.classList.toggle("active",i===j));
  current=i;
  const p=Math.round((i+1)/qs.length*100);
  fill.style.width=p+"%";
  txt.textContent=`Question ${i+1} of ${qs.length}`;
  pct.textContent=`${p}% complete`;
  back.disabled=i===0;
  requestAnimationFrame(()=>{
    const activeQuestion=qs[i];
    const header=document.querySelector(".site-header");
    const progress=document.querySelector(".snapshot-progress-wrap");
    const offset=(header?.offsetHeight||78)+(progress?.offsetHeight||42)+25;
    const targetTop=activeQuestion.getBoundingClientRect().top+window.scrollY-offset;
    window.scrollTo({top:Math.max(0,targetTop),behavior:"smooth"});
  });
 };
 qs.forEach((q,i)=>q.querySelectorAll("input").forEach(input=>input.addEventListener("change",()=>{q.querySelectorAll("label").forEach(l=>l.classList.toggle("selected",l.contains(input)&&input.checked));setTimeout(()=>{if(i<qs.length-1)show(i+1);else{
    const formData = Object.fromEntries(
        new FormData(form).entries()
    );
    const name = document.getElementById("name").value.trim();
    const phone = document.getElementById("phone").value.trim();

    sendSnapshotToBackend(formData, name, phone);

    save(A, calculate(formData));
    location.href = "results.html";
  }},260);})));
 back.addEventListener("click",()=>current>0&&show(current-1)); show(0);
}
const page=document.querySelector("[data-results-page]");
if(page){
 const r=load(A); if(!r.total){location.href="assessment.html";return;}
 const put=(s,t)=>{const e=document.querySelector(s);if(e)e.textContent=t};
 put("[data-total-score]",r.total);document.querySelector("[data-score-ring]").style.setProperty("--score",r.total);
 put("[data-strength-title]",labels[r.strength]);put("[data-strength-copy]",`At ${r.dimensions[r.strength]}/100, this is the strongest part of your current foundation.`);
 put("[data-opportunity-title]",labels[r.opportunity]);put("[data-opportunity-copy]",`At ${r.dimensions[r.opportunity]}/100, focused support here may create the biggest difference.`);
 const summaries={
 recovery:["Your body may not need more discipline. It may need better recovery.","Sleep quality, morning freshness and stress load may be making hunger, energy and consistency harder than they need to feel."],
 metabolic:["Steadier energy may be the key that unlocks everything else.","When energy is unpredictable, healthy choices can feel much harder. A more supportive daily rhythm may help."],
 nutrition:["Your cravings may be information—not a lack of willpower.","Cravings can be shaped by meal structure, recovery, stress and daily routines. The answer is often better support, not stricter restriction."],
 behaviour:["Consistency may matter more than finding the perfect plan.","Starting, stopping or feeling discouraged may be creating more friction than the plan itself."],
 confidence:["Rebuilding trust in yourself may be the most important first step.","Emotional wellbeing and self-trust deserve a central place in your health strategy."]
 }[r.opportunity];
 put("[data-summary-title]",summaries[0]);put("[data-summary-copy]",summaries[1]);
 const contrib={
 recovery:["Sleep quality","Morning freshness","Daily stress load"],metabolic:["Energy fluctuations","Recovery patterns","Changing body signals"],
 nutrition:["Cravings","Meal rhythm","Stress and sleep interactions"],behaviour:["Stop-start cycles","Slow feedback","All-or-nothing expectations"],
 confidence:["Body trust","Frustration","Feeling stuck or disconnected"]
 }[r.opportunity];
 document.querySelector("[data-contributors]").innerHTML=contrib.map(x=>`<span>✓ ${x}</span>`).join("");
 const p=profiles[r.bodyProfile];document.querySelector("[data-body-profile]").innerHTML=`<span class="result-kicker">Your body-change profile</span><h3>${p[0]}</h3><p>${p[1]}</p>`;
 document.querySelector("[data-dimension-grid]").innerHTML=Object.entries(r.dimensions).sort((a,b)=>b[1]-a[1]).map(([k,v])=>`<article class="dimension-card ${k===r.strength?"is-strength":""} ${k===r.opportunity?"is-opportunity":""}"><div class="dimension-card-top"><h3>${labels[k]}</h3><strong>${v}</strong></div><div class="dimension-bar"><span style="width:${v}%"></span></div><p>${descriptions[k]}</p>${k===r.strength?"<small>Strongest area</small>":""}${k===r.opportunity?"<small>Biggest opportunity</small>":""}</article>`).join("");
 const band=r.total<42?"high":r.total<65?"building":"steady";
 let rec;
 if(band==="high")rec=["The NourisHer Transformation™","Several areas appear to be interacting at once. A personalised strategy may help you stop guessing and focus on what matters most.",["Individual review of your routines and priorities","A strategy tailored to your body and real life","Private accountability and adjustments"],"Apply to Transformation →","join.html","Explore Foundations","foundations.html"];
 else if(band==="building"&&r.opportunity==="behaviour")rec=["NourisHer Foundations","Your biggest need appears to be structure and consistency. Foundations may be the best place to build momentum with guided habits, challenges and community.",["Build repeatable habits without perfection","Focus on the highest-impact actions","Use group support to create momentum"],"Explore Foundations →","foundations.html","See Transformation","transformation.html"];
 else if(band==="building")rec=["Choose the level of support that fits you","You have useful strengths, but one or two areas may need focused attention. Foundations builds structure; Transformation offers deeper personalisation.",["Focus on one or two high-impact areas","Choose group structure or 1:1 coaching","Build on what is already working"],"Explore Transformation →","transformation.html","See Foundations","foundations.html"];
 else rec=["Build on the strong foundation you already have","Your snapshot shows several supportive habits. Your next step is likely refinement through Foundations or personalised coaching if results still feel slow.",["Protect the habits already working","Refine the lowest-scoring area","Use personalisation if effort and results feel mismatched"],"Explore Foundations →","foundations.html","Explore Transformation","transformation.html"];
 put("[data-recommendation-title]",rec[0]);put("[data-recommendation-copy]",rec[1]);document.querySelector("[data-recommendation-points]").innerHTML=rec[2].map(x=>`<li>${x}</li>`).join("");
 const a=document.querySelector("[data-primary-recommendation]"),b=document.querySelector("[data-secondary-recommendation]");a.textContent=rec[3];a.href=rec[4];b.textContent=rec[5];b.href=rec[6];
}
const app=document.querySelector("[data-application-form]");
if(app)app.addEventListener("submit",e=>{e.preventDefault();if(!app.checkValidity()){app.reportValidity();return;}const d=Object.fromEntries(new FormData(app).entries());d.createdAt=new Date().toISOString();d.snapshot=load(A);save(P,d);location.href="thank-you.html";});
})();
