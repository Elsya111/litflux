// Coordinates illustrate choices, not a universal layout. No application code runs here.
const data=(id,title)=>({id,type:'data',title});
const business=(id,title,source)=>({id,type:'business',title,sources:[source]});
const edge=(id,from,to,label='')=>({id,from,to,label,type:'data',timing:'immediate'});
function horizontal(s,id,from,to,y,label=''){
  const a=s.nodeBox(from),b=s.nodeBox(to),right=b.x>a.x;
  const first=right?a.right:a.left,last=right?b.left:b.right;
  const options={sides:right?['right','left']:['left','right']};
  if(label){
    options.noteAt=[(first+last)/2,y];options.noteWidth=Math.abs(last-first)-26;
    // Includes the note background, useful if another row is placed nearby.
    const measured=s.measure(label,{maxWidth:options.noteWidth});
    if(measured.boxHeight>100)throw Error('This reference needs a wider label corridor');
  }
  s.edge(id,options);
}
const chain={
  objects:[data('text','原始文本'),business('prepare','清理并拆分词语','src:5'),data('words','词语列表'),
    business('measure','统计总数与不同词数','src:6'),data('metrics','统计结果'),business('format','生成可读摘要','src:7'),data('reply','摘要文本')],
  relations:[edge('a','text','prepare','待整理文本'),edge('b','prepare','words','清理后的完整词语'),edge('c','words','measure','词语作为统计输入'),edge('d','measure','metrics','总数与不同词数'),edge('e','metrics','format','用于生成摘要的统计'),edge('f','format','reply','可读摘要')],
  draw(s){
    // Fold at the stage boundary: first row rightwards, next row leftwards.
    s.node('text',100,110).node('prepare',380,110).node('words',680,110)
      .node('measure',680,350).node('metrics',380,350).node('format',100,350).node('reply',100,550);
    horizontal(s,'a','text','prepare',110,'待整理文本');horizontal(s,'b','prepare','words',110,'清理后的完整词语');
    s.edge('c',{sides:['bottom','top'],noteAt:[680,230],noteWidth:160});
    horizontal(s,'d','measure','metrics',350,'总数与不同词数');horizontal(s,'e','metrics','format',350,'用于生成摘要的统计');
    s.edge('f',{sides:['bottom','top'],noteAt:[100,455],noteWidth:150});
  }
};
const straight={...chain,draw(s){
  // Same facts and line timing; a wider single row can suit a wide display.
  chain.objects.forEach((o,i)=>s.node(o.id,100+i*285,140));
  chain.relations.forEach(r=>horizontal(s,r.id,r.from,r.to,140,r.label));
}};
const parallel={
  objects:[data('words','词语列表'),business('count','统计词语总数','src:11'),business('unique','统计不同词数','src:12'),data('counted','词语总数'),data('distinct','不同词数'),business('merge','组合统计结果','src:13'),data('result','统计结果')],
  relations:[edge('a','words','count','全部词语'),edge('b','words','unique','同一份词语'),edge('c','count','counted','总数'),edge('d','unique','distinct','不同词数'),edge('e','counted','merge','总数参与组合'),edge('f','distinct','merge','不同词数参与组合'),edge('g','merge','result')],
  draw(s){
    s.node('words',100,260).node('count',370,120).node('unique',370,400).node('counted',640,120).node('distinct',640,400).node('merge',950,260).node('result',1220,260);
    s.edge('a',{sides:['right','left'],via:[[230,260],[230,120]],noteAt:[230,190],noteWidth:100});
    s.edge('b',{sides:['right','left'],via:[[230,260],[230,400]],noteAt:[230,330],noteWidth:100});
    horizontal(s,'c','count','counted',120,'总数');horizontal(s,'d','unique','distinct',400,'不同词数');
    s.edge('e',{sides:['right','left'],via:[[800,120],[800,260]],noteAt:[800,180],noteWidth:120});
    s.edge('f',{sides:['right','left'],via:[[850,400],[850,260]],noteAt:[850,350],noteWidth:130});
    horizontal(s,'g','merge','result',260);
  }
};
const branch={
  objects:[data('words','词语列表'),{id:'usable',type:'decision',title:'有可用词语吗？',choices:[{id:'yes',label:'有词语'},{id:'no',label:'没有词语'}],sources:['src:17']},business('count','返回词语数量','src:18'),business('refuse','返回无词语说明','src:19'),data('result','词语数量'),data('refused','无词语说明')],
  relations:[edge('input','words','usable','判断是否为空'),{id:'yes',from:'usable',to:'count',type:'control',branch:'yes',label:'有词语'},
    {id:'no',from:'usable',to:'refuse',type:'control',branch:'no',label:'没有词语'},
    {...edge('kept','words','count','通过判断后使用原词语'),timing:'deferred',when:{usable:'yes'}},edge('counted','count','result'),edge('rejected','refuse','refused')],
  draw(s){
    s.node('words',100,200).node('usable',390,200).node('count',730,200).node('refuse',390,430).node('result',1020,200).node('refused',730,430);
    horizontal(s,'input','words','usable',200,'判断是否为空');horizontal(s,'yes','usable','count',200,'有词语');
    s.edge('kept',{sides:['top','top'],via:[[100,55],[730,55]],noteAt:[420,55],noteWidth:240});
    s.edge('no',{sides:['bottom','top'],noteAt:[390,330],noteWidth:150});
    horizontal(s,'counted','count','result',200);horizontal(s,'rejected','refuse','refused',430);
  }
};
const loop={
  objects:[business('init','初始化累计列表','src:23'),{id:'more',type:'decision',title:'还有词语吗？',choices:[{id:'yes',label:'继续一轮'},{id:'no',label:'结束循环'}],sources:['src:24']},business('append','计算长度并追加','src:25'),{id:'counts',type:'resource',title:'累计长度列表',sources:['src:23-25']},business('finish','返回累计长度','src:26'),data('result','累计长度')],
  relations:[{id:'start',from:'init',to:'more',type:'control',label:'开始遍历'},
    {id:'yes',from:'more',to:'append',type:'control',branch:'yes',label:'读取下一词语'},
    {id:'no',from:'more',to:'finish',type:'control',branch:'no',label:'已经遍历完'},
    {id:'init-state',from:'init',to:'counts',type:'effect',label:'创建空列表'},
    {id:'write',from:'append',to:'counts',type:'effect',label:'追加本轮长度'},
    {id:'read',from:'counts',to:'finish',type:'effect',label:'读取累计结果'},
    {id:'again',from:'append',to:'more',type:'loop',label:'继续下一轮'},edge('output','finish','result')],
  draw(s){
    s.node('init',110,180).node('more',430,180).node('append',770,180).node('counts',770,450).node('finish',430,450).node('result',110,450);
    horizontal(s,'start','init','more',180,'开始遍历');horizontal(s,'yes','more','append',180,'读取下一词语');
    s.edge('no',{sides:['bottom','top'],noteAt:[430,320],noteWidth:160});
    s.edge('init-state',{sides:['left','bottom'],via:[[15,180],[15,570],[770,570]],noteAt:[440,570],noteWidth:160});
    s.edge('write',{sides:['bottom','top'],noteAt:[770,320],noteWidth:160});
    horizontal(s,'read','counts','finish',450,'读取累计结果');horizontal(s,'output','finish','result',450);
    s.edge('again',{sides:['top','top'],via:[[770,55],[430,55]],noteAt:[600,55],noteWidth:180});
  }
};
module.exports={title:'布局参考 · 多种合理画法',summary:'同一事实可有不同布局；尺寸查询与测量帮助作者减少坐标试错。',scope:'layout.py 的四个教学函数，静态阅读，不执行函数。',language:'zh',files:{src:'layout.py'},workflows:[
  {id:'fold',title:'主链折返',entry:{trigger:'report(text)',sources:['src:4-7']},flow:chain},
  {id:'row',title:'同一主链的单行画法',entry:{trigger:'report(text)',sources:['src:4-7']},flow:straight},
  {id:'parallel',title:'并行汇合',entry:{trigger:'inspect_words(words)',sources:['src:10-13']},flow:parallel},
  {id:'branch',title:'互斥分支',entry:{trigger:'accept(words)',sources:['src:16-19']},flow:branch},
  {id:'loop',title:'循环与共享状态',entry:{trigger:'collect(words)',sources:['src:22-26']},flow:loop}
]};
