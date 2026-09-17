'use strict';
const escapeHTML = v => String(v || '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
fetch('/openapi.json').then(r => r.json()).then(doc => {
    const cards = [];
    for (const [path, methods] of Object.entries(doc.paths))
        for (const [method, item] of Object.entries(methods)) {
            if (!['get', 'post', 'put', 'patch', 'delete'].includes(method))
                continue;
            cards.push(`<section class="card"><div class="row wrap"><span class="pill">${method.toUpperCase()}</span><code>${escapeHTML(path)}</code></div><p class="subtitle">${escapeHTML(item.summary)}</p><details style="margin-top:15px"><summary>请求参数与响应契约</summary><pre style="white-space:pre-wrap;word-break:break-word;font-size:12px">${escapeHTML(JSON.stringify({ parameters: item.parameters, requestBody: item.requestBody, responses: item.responses }, null, 2))}</pre></details></section>`);
        }
    document.querySelector('#reference').innerHTML = `<p class="subtitle" style="margin-bottom:20px">${cards.length} 个接口操作 · 版本 ${escapeHTML(doc.info.version)}</p>` + cards.join('');
}).catch(error => { document.querySelector('#reference').textContent = '加载失败：' + error.message; });
