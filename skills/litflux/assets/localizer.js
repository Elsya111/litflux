(root, state, messages) => {
  const source = new WeakMap();
  const attributes = ['title', 'label', 'aria-label', 'aria-valuetext', 'placeholder', 'data-tooltip', 'data-description'];
  let scheduled = false;
  const dictionary = {...messages};
  const parts = Object.keys(dictionary).filter(key => key.length > 1 && /[\u3400-\u9fff]/.test(key)).sort((a,b) => b.length-a.length);
  const pattern = new RegExp(parts.map(key => key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
  function text(value) {
    const raw = String(value ?? '');
    if (state.language !== 'en') return raw;
    if (Object.hasOwn(dictionary, raw)) return dictionary[raw];
    if (!/[\u3400-\u9fff，；。、「」：]/.test(raw)) return raw;
    // Match reviewed phrases only. Source identifiers, paths and code are never translated.
    const translated = raw.replace(pattern, match => dictionary[match]);
    return /[\u3400-\u9fff]/.test(translated) ? raw : translated.replace(/[，；。、「」：]/g, mark => ({'，':', ','；':'; ','。':'.','、':', ','「':'"','」':'"','：':': '}[mark]));
  }
  function update(node, key, value, write) {
    let record = source.get(node);
    if (!record) { record = {}; source.set(node, record); }
    const old = record[key];
    const raw = old && old.output === value ? old.raw : value;
    const output = text(raw);
    record[key] = {raw, output};
    if (output !== value) write(output);
  }
  function apply() {
    observer.disconnect();
    try {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT, {
        acceptNode(node) {
          const el = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
          return el.closest('script,style,pre,code,[data-no-translate],.sf-signature') ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT;
        }
      });
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (node.nodeType === Node.TEXT_NODE) update(node, 'text', node.nodeValue, value => {node.nodeValue = value;});
        else for (const name of attributes) if (node.hasAttribute(name)) update(node, name, node.getAttribute(name), value => node.setAttribute(name, value));
      }
      root.lang = state.language === 'zh' ? 'zh-CN' : 'en';
      document.documentElement.lang = root.lang;
    } finally { observer.observe(root, {subtree:true, childList:true, characterData:true, attributes:true, attributeFilter:attributes}); }
  }
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    queueMicrotask(() => {scheduled = false; apply();});
  });
  return {text, apply};
}
