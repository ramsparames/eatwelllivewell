from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta
from io import BytesIO
import re
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from app.database import get_connection

PURPLE=colors.HexColor('#5B0E91'); GOLD=colors.HexColor('#D7A514'); CREAM=colors.HexColor('#FFF9EE'); LILAC=colors.HexColor('#F7F0FB'); INK=colors.HexColor('#2B2430'); MUTED=colors.HexColor('#716777'); BORDER=colors.HexColor('#E8DDED')

def _safe(v): return re.sub(r'[^A-Za-z0-9_-]+','_',v.strip()).strip('_') or 'client'
def _fmt(v,d=1,s=''):
    if v is None:return '-'
    try:return f'{float(v):.{d}f}'.rstrip('0').rstrip('.')+s
    except:return str(v)
def _delta(a,b,s=''):
    if a is None or b is None:return '-'
    d=float(b)-float(a); return ('+' if d>0 else '')+f'{d:.1f}'+s

def _bounds(client,period,today):
    start=client.get('start_date') or today
    if period=='since_start': return start,today,'Since start'
    current=max(1,((today-start).days//7)+1); first=max(1,current-3)
    return start+timedelta(days=(first-1)*7),today,'Last 4 weeks'

def _fetch(client_id,start,end):
    d={}
    with get_connection() as con:
      with con.cursor() as c:
        c.execute('SELECT * FROM clients WHERE id=%s LIMIT 1',(client_id,)); d['client']=dict(c.fetchone())
        c.execute('''SELECT s.tracked_on,t.steps,t.weight_kg FROM client_portal_daily_submissions s LEFT JOIN client_daily_tracking t ON t.client_id=s.client_id AND t.tracked_on=s.tracked_on WHERE s.client_id=%s AND s.tracked_on BETWEEN %s AND %s ORDER BY s.tracked_on''',(client_id,start,end)); d['daily']=[dict(r) for r in c.fetchall()]
        c.execute('''SELECT p.id,p.action_name,p.target_count,p.target_unit,p.start_date,p.end_date,COUNT(l.id) FILTER (WHERE l.completed=TRUE AND l.tracked_on BETWEEN %s AND %s) completed_count,COUNT(l.id) FILTER (WHERE l.tracked_on BETWEEN %s AND %s) logged_count FROM client_action_plans p LEFT JOIN client_action_daily_logs l ON l.action_id=p.id WHERE p.client_id=%s AND p.start_date<=%s AND (p.end_date IS NULL OR p.end_date>=%s) GROUP BY p.id ORDER BY p.start_date,p.id''',(start,end,start,end,client_id,end,start)); d['actions']=[dict(r) for r in c.fetchall()]
        c.execute('SELECT * FROM client_measurements WHERE client_id=%s AND measured_on BETWEEN %s AND %s ORDER BY measured_on,id',(client_id,start,end)); d['measurements']=[dict(r) for r in c.fetchall()]
        c.execute('SELECT * FROM client_weekly_checkins WHERE client_id=%s AND call_date BETWEEN %s AND %s ORDER BY call_date,id',(client_id,start,end)); d['checkins']=[dict(r) for r in c.fetchall()]
        try:
            c.execute('SELECT * FROM client_weekly_reflections WHERE client_id=%s AND week_start BETWEEN %s AND %s ORDER BY week_start',(client_id,start,end)); d['reflections']=[dict(r) for r in c.fetchall()]
        except Exception: con.rollback(); d['reflections']=[]
        try:
            c.execute('SELECT enabled,protein_target_g,carbs_target_g,fat_target_g,fibre_target_g FROM client_macro_settings WHERE client_id=%s LIMIT 1',(client_id,)); r=c.fetchone(); d['macro_settings']=dict(r) if r else {'enabled':False}
            c.execute('SELECT tracked_on,protein_g,carbs_g,fat_g,fibre_g FROM client_macro_logs WHERE client_id=%s AND tracked_on BETWEEN %s AND %s ORDER BY tracked_on',(client_id,start,end)); d['macros']=[dict(r) for r in c.fetchall()]
        except Exception: con.rollback(); d['macro_settings']={'enabled':False}; d['macros']=[]
    return d

def _styles():
    b=getSampleStyleSheet(); return {'title':ParagraphStyle('t',parent=b['Title'],fontName='Helvetica-Bold',fontSize=24,leading=29,textColor=PURPLE),'sub':ParagraphStyle('s',parent=b['Normal'],fontSize=10.5,leading=15,textColor=MUTED),'h2':ParagraphStyle('h2x',parent=b['Heading2'],fontName='Helvetica-Bold',fontSize=15,leading=19,textColor=PURPLE,spaceBefore=6,spaceAfter=8),'h3':ParagraphStyle('h3x',parent=b['Heading3'],fontName='Helvetica-Bold',fontSize=11,leading=14,textColor=INK,spaceAfter=4),'body':ParagraphStyle('bx',parent=b['BodyText'],fontSize=9.5,leading=14,textColor=INK),'metric':ParagraphStyle('mx',parent=b['BodyText'],fontName='Helvetica-Bold',fontSize=15,leading=18,textColor=PURPLE,alignment=TA_CENTER),'label':ParagraphStyle('lx',parent=b['BodyText'],fontSize=7.8,leading=10,textColor=MUTED,alignment=TA_CENTER),'white':ParagraphStyle('wx',parent=b['BodyText'],fontName='Helvetica-Bold',fontSize=9,textColor=colors.white)}
def _card(label,value,s): return Table([[Paragraph(value,s['metric'])],[Paragraph(label,s['label'])]],colWidths=[40*mm],rowHeights=[11*mm,8*mm],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),LILAC),('BOX',(0,0),(-1,-1),.7,BORDER),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
def _chart(points,title,s):
    if len(points)<2:return None
    dr=Drawing(165*mm,50*mm); ch=HorizontalLineChart(); ch.x=8*mm; ch.y=8*mm; ch.width=150*mm; ch.height=33*mm; ch.data=[[float(v) for _,v in points]]; ch.categoryAxis.categoryNames=[d.strftime('%d %b') for d,_ in points]; ch.categoryAxis.labels.fontSize=6.5; ch.categoryAxis.labels.angle=30; ch.valueAxis.labels.fontSize=7; ch.lines[0].strokeColor=PURPLE; ch.lines[0].strokeWidth=2; dr.add(ch); return KeepTogether([Paragraph(title,s['h3']),dr])
def _hf(canvas,doc,name,label):
    canvas.saveState(); w,h=A4; canvas.setFillColor(PURPLE); canvas.rect(0,h-11*mm,w,11*mm,fill=1,stroke=0); canvas.setFillColor(colors.white); canvas.setFont('Helvetica-Bold',9); canvas.drawString(18*mm,h-7*mm,'NourisHer | Eat Well Live Well'); canvas.setFillColor(MUTED); canvas.setFont('Helvetica',7.5); canvas.drawString(18*mm,10*mm,f'{name} - {label} milestone review'); canvas.drawRightString(w-18*mm,10*mm,f'Page {doc.page}'); canvas.restoreState()

def build_client_progress_pdf(client_id:int,period:str='last4'):
    today=date.today()
    with get_connection() as con:
      with con.cursor() as c:
        c.execute('SELECT * FROM clients WHERE id=%s LIMIT 1',(client_id,)); row=c.fetchone()
        if not row: raise ValueError('Client not found')
        client=dict(row)
    start,end,label=_bounds(client,period,today); d=_fetch(client_id,start,end); s=_styles(); name=d['client'].get('name') or 'Client'; buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4,rightMargin=18*mm,leftMargin=18*mm,topMargin=19*mm,bottomMargin=18*mm,title=f'{name} Progress Review'); story=[]
    story += [Spacer(1,4*mm),Paragraph(f"{name}'s Progress Review",s['title']),Paragraph(f'{label} | {start.strftime("%d %b %Y")} - {end.strftime("%d %b %Y")}',s['sub']),Spacer(1,6*mm)]
    daily=d['daily']; submitted=len({r['tracked_on'] for r in daily}); possible=max(1,(end-start).days+1); pct=round(submitted/possible*100); steps=[r['steps'] for r in daily if r.get('steps') is not None]; avgsteps=round(sum(steps)/len(steps)) if steps else None; weights=[(r['tracked_on'],r['weight_kg']) for r in daily if r.get('weight_kg') is not None]; comp=sum(int(a.get('completed_count') or 0) for a in d['actions']); logged=sum(int(a.get('logged_count') or 0) for a in d['actions']); adh=round(comp/logged*100) if logged else None
    cards=[_card('CLIENT UPDATES',f'{submitted}/{possible} ({pct}%)',s),_card('ACTION CONSISTENCY',f'{adh}%' if adh is not None else '-',s),_card('AVERAGE STEPS',f'{avgsteps:,}' if avgsteps is not None else '-',s),_card('WEIGHT CHANGE',_delta(weights[0][1],weights[-1][1],' kg') if len(weights)>=2 else '-',s)]; story.append(Table([cards],colWidths=[42*mm]*4,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),1),('RIGHTPADDING',(0,0),(-1,-1),1)]))); story += [Spacer(1,7*mm),Paragraph('Progress at a glance',s['h2'])]
    rows=[['Metric','Start','Latest','Change']]
    if weights: rows.append(['Weight',_fmt(weights[0][1],1,' kg'),_fmt(weights[-1][1],1,' kg'),_delta(weights[0][1],weights[-1][1],' kg') if len(weights)>=2 else '-'])
    ms=d['measurements']
    if ms:
      first,last=ms[0],ms[-1]
      for key,lab in [('waist_cm','Waist'),('hip_cm','Hip'),('chest_cm','Chest'),('lower_abdomen_cm','Lower abdomen'),('thigh_cm','Thigh'),('upper_arm_cm','Upper arm')]:
        if first.get(key) is not None or last.get(key) is not None: rows.append([lab,_fmt(first.get(key),1,' cm'),_fmt(last.get(key),1,' cm'),_delta(first.get(key),last.get(key),' cm')])
    if len(rows)==1: rows.append(['Measurements','No measurements recorded','-','-'])
    t=Table(rows,colWidths=[43*mm,43*mm,43*mm,39*mm],repeatRows=1); t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PURPLE),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5),('GRID',(0,0),(-1,-1),.5,BORDER),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,CREAM]),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])); story.append(t)
    ch=_chart(weights,'Weight trend',s)
    if ch: story += [Spacer(1,5*mm),ch]
    story += [PageBreak(),Spacer(1,4*mm),Paragraph('Consistency & coaching progress',s['title']),Paragraph('What the client has been practicing - and what deserves attention in the review conversation.',s['sub']),Spacer(1,5*mm),Paragraph('Actions',s['h2'])]
    agg=defaultdict(lambda:{'c':0,'l':0})
    for a in d['actions']: agg[a.get('action_name') or 'Action']['c']+=int(a.get('completed_count') or 0); agg[a.get('action_name') or 'Action']['l']+=int(a.get('logged_count') or 0)
    ar=[['Action','Completed','Consistency']]
    for n,v in agg.items(): ar.append([Paragraph(n,s['body']),str(v['c']),f"{round(v['c']/v['l']*100)}%" if v['l'] else '-'])
    if len(ar)==1: ar.append(['No action tracking recorded','-','-'])
    at=Table(ar,colWidths=[112*mm,28*mm,28*mm],repeatRows=1); at.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),PURPLE),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),8.5),('GRID',(0,0),(-1,-1),.45,BORDER),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LILAC]),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)])); story += [at,Spacer(1,5*mm)]
    mset=d.get('macro_settings') or {}; macros=d.get('macros') or []
    if mset.get('enabled') and macros:
      def avg(f):
        vals=[float(r[f]) for r in macros if r.get(f) is not None]; return sum(vals)/len(vals) if vals else None
      mr=[['Macro','Average','Target'],['Protein',_fmt(avg('protein_g'),1,' g'),_fmt(mset.get('protein_target_g'),0,' g')],['Carbs',_fmt(avg('carbs_g'),1,' g'),_fmt(mset.get('carbs_target_g'),0,' g')],['Fat',_fmt(avg('fat_g'),1,' g'),_fmt(mset.get('fat_target_g'),0,' g')],['Fibre',_fmt(avg('fibre_g'),1,' g'),_fmt(mset.get('fibre_target_g'),0,' g')]]; mt=Table(mr,colWidths=[56*mm]*3); mt.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GOLD),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('GRID',(0,0),(-1,-1),.45,BORDER),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,CREAM]),('ALIGN',(1,1),(-1,-1),'CENTER'),('FONTSIZE',(0,0),(-1,-1),8.5),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)])); story += [Paragraph('Nutrition tracking',s['h2']),mt,Spacer(1,5*mm)]
    checks=d.get('checkins') or []; wins=[x['wins'] for x in checks if x.get('wins')]; struggles=[x['struggles'] for x in checks if x.get('struggles')]; improvements=[x['improvements_needed'] for x in checks if x.get('improvements_needed')]
    def box(title,items): return Table([[Paragraph(title,s['h3'])],[Paragraph('<br/>'.join('• '+str(x) for x in items[-4:]) if items else 'No coaching notes recorded in this period.',s['body'])]],colWidths=[81*mm],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),CREAM),('BOX',(0,0),(-1,-1),.6,BORDER),('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    story += [Paragraph('Coaching themes',s['h2']),Table([[box('Wins',wins),box('Still working on',struggles or improvements)]],colWidths=[84*mm]*2,style=TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))]
    story += [PageBreak(),Spacer(1,4*mm),Paragraph('Milestone review conversation',s['title']),Paragraph("Use this page during the call to connect the data with the client's lived experience and choose the next focus.",s['sub']),Spacer(1,6*mm)]
    refs=d.get('reflections') or []
    if refs:
      r=refs[-1]; parts=[]
      for f,l in [('wins','Latest win'),('challenge','Current challenge'),('help_needed','Support requested')]:
        if r.get(f): parts.append(f'<b>{l}:</b> {r[f]}')
      if r.get('energy_score') is not None: parts.append(f'<b>Energy:</b> {r["energy_score"]}/10')
      if parts: story += [Table([[Paragraph('Client voice',s['h3'])],[Paragraph('<br/>'.join(parts),s['body'])]],colWidths=[168*mm],style=TableStyle([('BACKGROUND',(0,0),(-1,-1),LILAC),('BOX',(0,0),(-1,-1),.7,BORDER),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)])),Spacer(1,6*mm)]
    for p in ['What has improved most since the last milestone?','What is feeling easier or more natural now?','Where is consistency still breaking down?','What should we continue?','What should we simplify, change or remove?','What is the single most important focus for the next phase?']:
      story += [Paragraph(p,s['h3']),Table([[''],['']],colWidths=[168*mm],rowHeights=[8*mm,8*mm],style=TableStyle([('LINEBELOW',(0,0),(-1,-1),.45,colors.HexColor('#D9CFDD'))])),Spacer(1,3*mm)]
    story += [Spacer(1,3*mm),Table([[Paragraph('Next milestone focus',s['white'])],[''],['']],colWidths=[168*mm],rowHeights=[9*mm,11*mm,11*mm],style=TableStyle([('BACKGROUND',(0,0),(-1,0),PURPLE),('BOX',(0,0),(-1,-1),.8,PURPLE),('LEFTPADDING',(0,0),(-1,-1),8),('VALIGN',(0,0),(-1,-1),'MIDDLE')]))]
    doc.build(story,onFirstPage=lambda c,x:_hf(c,x,name,label),onLaterPages=lambda c,x:_hf(c,x,name,label)); pdf=buf.getvalue(); fn=f'NourisHer_{_safe(name)}_{"Last_4_Weeks" if period=="last4" else "Since_Start"}_Progress.pdf'; return pdf,fn
