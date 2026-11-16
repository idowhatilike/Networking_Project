/* Thiết lập HTMX an toàn CSP, hộp thoại, đếm ngược và biểu đồ cho OpenGuard Kids */
(function () {
  if (window.htmx && window.htmx.config) {
    window.htmx.config.allowEval = false;
    window.htmx.config.includeIndicatorStyles = false;
  }

  function showRequestError(message) {
    const toastArea = document.getElementById('toast-area') ;
    if (!toastArea) return ;
    const alert = document.createElement('div') ;
    alert.className = 'form-error' ;
    alert.setAttribute('role' , 'alert') ;
    alert.textContent = message ;
    toastArea.replaceChildren(alert) ;
  }

  function initReportCharts(root) {
    const scope = root && root.querySelectorAll ? root : document;
    const canvases = Array.from(scope.querySelectorAll('canvas.ogk-report-chart')) ;
    if (scope.matches && scope.matches('canvas.ogk-report-chart')) canvases.unshift(scope) ;
    canvases.forEach(function (canvas) {
      if (canvas._chartInstance) return ;
      if (typeof window.Chart !== 'function') return;
      const labels = (canvas.getAttribute('data-labels') || '').split(',').filter(Boolean);
      const edu = (canvas.getAttribute('data-education') || '').split(',').map(Number);
      const ent = (canvas.getAttribute('data-entertainment') || '').split(',').map(Number);
      const gam = (canvas.getAttribute('data-gaming') || '').split(',').map(Number);
      canvas._chartInstance = new window.Chart(canvas, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [
            { label: 'Giáo dục (phút)', data: edu },
            { label: 'Giải trí (phút)', data: ent },
            { label: 'Trò chơi (phút)', data: gam }
          ]
        }
      });
    });
  }

  function initCountdowns() {
    document.querySelectorAll('[data-countdown-sec]').forEach(function (el) {
      if (el._timerStarted) return;
      el._timerStarted = true;
      let remain = parseInt(el.getAttribute('data-countdown-sec') || '0', 10);
      const timer = setInterval(function () {
        if (remain <= 0) {
          el.textContent = '00:00 (Đã hết hạn)';
          clearInterval(timer);
          return;
        }
        remain -= 1;
        const m = String(Math.floor(remain / 60)).padStart(2, '0');
        const s = String(remain % 60).padStart(2, '0');
        el.textContent = m + ':' + s;
      }, 1000);
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.body.addEventListener('htmx:beforeCleanupElement' , function (event) {
      const canvas = event.detail.elt ;
      if (canvas._chartInstance) {
        canvas._chartInstance.destroy() ;
        canvas._chartInstance = null ;
      }
    }) ;

    document.body.addEventListener('htmx:responseError' , function (event) {
      const messages = {
        401 : 'Phiên truy cập đã hết hiệu lực. Hãy mở lại từ biểu tượng khay hệ thống.' ,
        403 : 'Bạn không có quyền thực hiện thao tác này.' ,
        404 : 'Không tìm thấy nội dung hoặc yêu cầu này.' ,
        422 : 'Dữ liệu chưa hợp lệ. Hãy kiểm tra lại nội dung đã nhập.' ,
        500 : 'Máy chủ gặp lỗi. Hãy thử lại sau.'
      } ;
      showRequestError(messages[event.detail.xhr.status] || 'Không thể hoàn tất yêu cầu.') ;
    }) ;
    document.body.addEventListener('htmx:sendError' , function () {
      showRequestError('Mất kết nối với máy chủ. Hãy kiểm tra mạng rồi thử lại.') ;
    }) ;

    document.body.addEventListener('htmx:configRequest', function (e) {
      const meta = document.querySelector('meta[name="csrf-token"]');
      if (meta && e.detail && e.detail.headers) {
        e.detail.headers['X-CSRF-Token'] = meta.getAttribute('content') || '';
      }
    });

    document.body.addEventListener('click', function (e) {
      const openBtn = e.target.closest('[data-open-modal]');
      if (openBtn) {
        const modalId = openBtn.getAttribute('data-open-modal');
        const dlg = document.getElementById(modalId);
        if (dlg && typeof dlg.showModal === 'function') {
          dlg.showModal();
        }
        return;
      }

      const closeBtn = e.target.closest('[data-close-modal]');
      if (closeBtn) {
        const modalId = closeBtn.getAttribute('data-close-modal');
        const dlg = modalId ? document.getElementById(modalId) : closeBtn.closest('dialog');
        if (dlg && typeof dlg.close === 'function') {
          dlg.close();
        }
        return;
      }

      const dismissBtn = e.target.closest('[data-dismiss-alert]');
      if (dismissBtn) {
        const banner = dismissBtn.closest('.alert-banner');
        if (banner) {
          banner.remove();
        }
        return;
      }

      const fillBtn = e.target.closest('[data-fill-target]');
      if (fillBtn) {
        const targetId = fillBtn.getAttribute('data-fill-target');
        const fillText = fillBtn.getAttribute('data-fill-text') || '';
        const inputEl = document.getElementById(targetId);
        if (inputEl) {
          inputEl.value = fillText;
          inputEl.focus();
        }
      }
    });

    initCountdowns();
  });

  if (window.htmx && typeof window.htmx.onLoad === 'function') {
    window.htmx.onLoad(function (content) {
      initReportCharts(content);
    });
  }
})();
