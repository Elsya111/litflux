// A source-backed resource key, not an execution-order diagram.
module.exports={
  title:'资源与源码 · 符号参考',language:'zh',summary:'对照 save_report() 中的资源及其作用。图标由工具根据类别选择。',scope:'只展示函数中的资源角色，不把这些资源串成执行步骤。',files:{source:'resources.py'},
  workflows:[{id:'resources',title:'资源类别与源码对应',entry:{trigger:'save_report(directory, config, connection, storage, text)',sources:['source:5-14']},flow:{
    objects:[
      {id:'db',type:'resource',resourceKind:'database',title:'报告数据库',text:'保存报告正文的数据库。save_report() 通过传入的 connection 执行 INSERT；此处表示被写入的数据库，连接对象提供的调用能力可在执行图中另行解释。',sources:['source:10']},
      {id:'config',type:'resource',resourceKind:'config',title:'运行配置',text:'控制本次文件写入的编码。对应参数 config，读取 encoding 配置项；未设置时使用 UTF-8。它表示运行时配置，不特指某个配置文件。',sources:['source:5','source:9']},
      {id:'folder',type:'resource',resourceKind:'directory',title:'报告目录',text:'容纳 report.txt 的目录。对应 folder，由输入的 directory 转成 Path；写文件前会创建缺失的目录。',sources:['source:6-8']},
      {id:'file',type:'resource',resourceKind:'file',title:'报告文件',text:'保存正文的 report.txt 文件载体，对应 report_file。文件内容使用运行配置指定的编码写入；与路径值分别表示载体和定位信息。',sources:['source:8-9']},
      {id:'recent',type:'resource',resourceKind:'memory',title:'近期报告列表',text:'保存本次生成的报告路径。对应 recent 列表，先创建，再追加 report_file 的路径字符串，随后交给外部存储并返回。',sources:['source:11-14']},
      {id:'storage',type:'resource',title:'外部存储',text:'接收近期报告列表的外部存储载体，通过调用者传入的 storage.save() 写入。当前源码没有给出其具体实现，因此保留通用资源类别，不推断是文件还是数据库。',sources:['source:5','source:13']}
    ],relations:[],draw(s){
      [['db',180,130],['config',480,130],['folder',780,130],['file',180,340],['recent',480,340],['storage',780,340]].forEach(([id,x,y])=>s.node(id,x,y,{width:210,height:92}));
    }
  }}]
};
