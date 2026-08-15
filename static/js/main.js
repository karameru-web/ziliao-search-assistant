/* ============================================================
   资料搜索助手 · 前端交互
   1) 资料组卡片展开/收起
   2) 下载 / 复制链接 / 收藏 / 移除 / 系统打开
   3) 搜索结果勾选 + 全选 + 存入资料库
   4) 批量上传进度
   ============================================================ */

/* ---------- 1) 卡片展开/收起 ---------- */
document.querySelectorAll('.cluster-card').forEach(function (card) {
  card.addEventListener('click', function (e) {
    // 点击卡片里的链接、按钮或复选框时不触发折叠
    if (e.target.closest('a') || e.target.closest('button') || e.target.closest('input')) return;
    var panel = document.getElementById(card.dataset.target);
    if (!panel) return;
    var instance = bootstrap.Collapse.getOrCreateInstance(panel, {toggle: false});
    instance.toggle();
    card.classList.toggle('open');
  });
});

/* ---------- 2) 通用小工具 ---------- */
function rowMsg(btn, text, ok) {
  var row = btn.closest('.shelf-item') || btn.closest('.d-flex, div');
  var msg = row ? row.querySelector('.dl-msg') : null;
  if (!msg && row) {
    msg = document.createElement('span');
    msg.className = 'dl-msg small';
    row.appendChild(msg);
  }
  if (msg) {
    msg.textContent = text;
    msg.className = 'dl-msg small ' + (ok ? 'text-success' : 'text-danger');
    setTimeout(function () {
      if (msg.parentNode) msg.parentNode.removeChild(msg);
    }, 6000);
  }
}

function showToast(text, ok) {
  var old = document.querySelector('.app-toast');
  if (old) old.remove();
  var t = document.createElement('div');
  t.className = 'app-toast ' + (ok ? 'ok' : 'err');
  t.textContent = text;
  document.body.appendChild(t);
  setTimeout(function () { t.remove(); }, 4000);
}

function fallbackCopy(text, done) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.select();
  try { document.execCommand('copy'); } catch (e) { /* 忽略 */ }
  document.body.removeChild(ta);
  done();
}

function copyUrl(url, btn) {
  var done = function () { rowMsg(btn, '已复制链接', true); };
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(url).then(done).catch(function () {
      fallbackCopy(url, done);
    });
  } else {
    fallbackCopy(url, done);
  }
}

/* ---------- 3) 全局按钮事件 ---------- */
document.addEventListener('click', function (e) {
  var btn;

  btn = e.target.closest('.btn-copy-link');
  if (btn) {
    e.preventDefault();
    copyUrl(btn.dataset.url || '', btn);
    return;
  }

  btn = e.target.closest('.btn-download');
  if (btn && btn.id !== 'save-selected') {
    e.preventDefault();
    if (btn.disabled) return;
    btn.disabled = true;
    var oldHtml = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>下载中';
    fetch('/download', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        url: btn.dataset.url || '',
        title: btn.dataset.title || '',
        source: btn.dataset.source || ''
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btn.disabled = false;
        btn.innerHTML = oldHtml;
        rowMsg(btn, d.message || '下载失败，请查看原文手动保存', !!d.ok);
      })
      .catch(function () {
        btn.disabled = false;
        btn.innerHTML = oldHtml;
        rowMsg(btn, '下载失败，请查看原文手动保存', false);
      });
    return;
  }

  btn = e.target.closest('.btn-bookmark');
  if (btn) {
    e.preventDefault();
    fetch('/shelf/add', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        url: btn.dataset.url || '',
        title: btn.dataset.title || '',
        source: btn.dataset.source || ''
      })
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        rowMsg(btn, d.message || '收藏失败', !!d.ok);
      })
      .catch(function () {
        rowMsg(btn, '收藏失败', false);
      });
    return;
  }

  btn = e.target.closest('.btn-open-file');
  if (btn) {
    e.preventDefault();
    fetch('/open_file/' + (btn.dataset.rel || ''))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        showToast(d.message || '打开失败', !!d.ok);
      })
      .catch(function () {
        showToast('打开失败，请手动打开文件', false);
      });
    return;
  }

  btn = e.target.closest('.btn-remove-entry');
  if (btn) {
    e.preventDefault();
    fetch('/shelf/remove', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({id: btn.dataset.id || ''})
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (d.ok) {
          // 立即整页刷新，保证列表补位、不留空白
          window.location.reload();
        } else {
          rowMsg(btn, d.message || '移除失败', false);
        }
      })
      .catch(function () {
        rowMsg(btn, '移除失败', false);
      });
  }
});

/* ---------- 4) 搜索结果勾选 + 存入资料库 ---------- */
function updateSelectCount() {
  var n = document.querySelectorAll('.item-check:checked').length;
  var el = document.getElementById('select-count');
  if (el) el.textContent = '已选 ' + n + ' 条';
}

document.addEventListener('change', function (e) {
  if (e.target.classList && e.target.classList.contains('item-check')) {
    updateSelectCount();
  }
});

var btnSave = document.getElementById('save-selected');

document.addEventListener('click', function (e) {
  var gBtn;
  gBtn = e.target.closest('.group-select-all');
  if (gBtn) {
    var panel = document.getElementById(gBtn.dataset.group);
    if (panel) {
      panel.querySelectorAll('.item-check').forEach(function (c) { c.checked = true; });
    }
    updateSelectCount();
    return;
  }
  gBtn = e.target.closest('.group-select-none');
  if (gBtn) {
    var panel2 = document.getElementById(gBtn.dataset.group);
    if (panel2) {
      panel2.querySelectorAll('.item-check').forEach(function (c) { c.checked = false; });
    }
    updateSelectCount();
  }
});

if (btnSave) {
  btnSave.addEventListener('click', function () {
    var items = [];
    document.querySelectorAll('.item-check:checked').forEach(function (c) {
      items.push({url: c.dataset.url || '', title: c.dataset.title || '', source: c.dataset.source || ''});
    });
    if (!items.length) {
      showToast('请先勾选要存入资料库的条目', false);
      return;
    }
    btnSave.disabled = true;
    fetch('/shelf/add_many', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({items: items})
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        btnSave.disabled = false;
        showToast(d.message || '存入失败', !!d.ok);
        if (d.ok) {
          document.querySelectorAll('.item-check:checked').forEach(function (c) { c.checked = false; });
          updateSelectCount();
        }
      })
      .catch(function () {
        btnSave.disabled = false;
        showToast('存入失败，请重试', false);
      });
  });
}

/* ---------- 5) 上传评估：先上传、后勾选、再评估 ---------- */
var upForm = document.getElementById('upload-form');
if (upForm) {
  upForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var input = document.getElementById('files');
    var files = input && input.files ? input.files : [];
    if (!files.length) {
      showToast('请先选择要上传的文件', false);
      return;
    }
    var btn = upForm.querySelector('button[type=submit]');
    if (btn) btn.disabled = true;
    fetch('/upload/add', {method: 'POST', body: new FormData(upForm)})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (btn) btn.disabled = false;
        showToast(d.message || '上传失败，请重试', !!d.ok);
        if (d.ok) {
          // 刷新列表，让新文件出现在可勾选列表里
          window.location.reload();
        }
      })
      .catch(function () {
        if (btn) btn.disabled = false;
        showToast('上传失败，请重试', false);
      });
  });
}

function updateFileCount() {
  var n = document.querySelectorAll('.file-check:checked').length;
  var el = document.getElementById('file-count');
  if (el) el.textContent = '已选 ' + n + ' 份';
}

document.addEventListener('change', function (e) {
  if (e.target.classList && e.target.classList.contains('file-check')) {
    updateFileCount();
  }
});

var evalBtn = document.getElementById('evaluate-btn');
if (evalBtn) {
  evalBtn.addEventListener('click', function () {
    var ids = [];
    document.querySelectorAll('.file-check:checked').forEach(function (c) {
      ids.push(c.value);
    });
    if (ids.length < 2) {
      showToast('请先勾选至少两份资料进行对比', false);
      return;
    }
    var box = document.getElementById('eval-progress');
    var bar = document.getElementById('eval-progress-bar');
    var text = document.getElementById('eval-progress-text');
    box.classList.remove('d-none');
    bar.style.width = '5%';
    text.textContent = '正在评估第 0 / ' + ids.length + ' 份文件…';
    evalBtn.disabled = true;
    fetch('/upload/evaluate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ids: ids})
    })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) {
          evalBtn.disabled = false;
          showToast(d.message || '评估失败', false);
          return;
        }
        var job = d.job_id;
        var timer = setInterval(function () {
          fetch('/upload_status/' + job)
            .then(function (r) { return r.json(); })
            .then(function (s) {
              if (s.done) {
                clearInterval(timer);
                window.location.href = '/upload?job=' + job;
                return;
              }
              text.textContent = '正在评估第 ' + s.current + ' / ' + s.total + ' 份文件…';
              bar.style.width = Math.round((s.current / s.total) * 100) + '%';
            })
            .catch(function () { /* 下一轮再试 */ });
        }, 500);
      })
      .catch(function () {
        evalBtn.disabled = false;
        showToast('评估失败，请重试', false);
      });
  });
}

/* ---------- 6) 我的资料库 · 三段进度按钮 ---------- */
document.addEventListener('click', function (e) {
  var seg = e.target.closest('.progress-seg');
  if (!seg) return;
  e.preventDefault();
  var group = seg.closest('.progress-group');
  if (!group) return;
  var id = group.dataset.id;
  var status = seg.dataset.status;
  fetch('/progress/update', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({entry_id: id, status: status})
  })
    .then(function (r) { return r.json(); })
    .then(function (d) {
      if (d.ok) {
        group.querySelectorAll('.progress-seg').forEach(function (s) {
          s.classList.remove('active');
        });
        seg.classList.add('active');
        var saved = group.querySelector('.progress-saved');
        if (!saved) {
          saved = document.createElement('span');
          saved.className = 'progress-saved';
          group.appendChild(saved);
        }
        saved.textContent = '✓ 已保存';
        setTimeout(function () { saved.textContent = ''; }, 1200);
      } else {
        showToast(d.message || '保存失败', false);
      }
    })
    .catch(function () {
      showToast('保存失败，请重试', false);
    });
});

/* ---------- 7) 我的资料库 · 上传入口 ---------- */
var shelfUpForm = document.getElementById('shelf-upload-form');
if (shelfUpForm) {
  shelfUpForm.addEventListener('submit', function (e) {
    e.preventDefault();
    var input = document.getElementById('shelf-files');
    var files = input && input.files ? input.files : [];
    if (!files.length) {
      showToast('请先选择要上传的文件', false);
      return;
    }
    var btn = shelfUpForm.querySelector('button[type=submit]');
    if (btn) btn.disabled = true;
    fetch('/upload/add', {method: 'POST', body: new FormData(shelfUpForm)})
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (btn) btn.disabled = false;
        showToast(d.message || '上传失败，请重试', !!d.ok);
        if (d.ok) {
          window.location.reload();  // 刷新列表，新文件立即出现
        }
      })
      .catch(function () {
        if (btn) btn.disabled = false;
        showToast('上传失败，请重试', false);
      });
  });
}
