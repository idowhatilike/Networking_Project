/* Đồng bộ khoảng giờ chọn nhanh và ma trận lịch tuần 7x48 (336 ô 30 phút) */
(function () {
  const DAY_LABELS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

  function readRowsFromDom() {
    const rows = ['0'.repeat(48), '0'.repeat(48), '0'.repeat(48), '0'.repeat(48), '0'.repeat(48), '0'.repeat(48), '0'.repeat(48)];
    for (let d = 0; d < 7; d++) {
      const chars = [];
      for (let s = 0; s < 48; s++) {
        const btn = document.querySelector('button.slot[data-day="' + d + '"][data-slot="' + s + '"]');
        const active = btn && btn.getAttribute('aria-pressed') === 'true';
        chars.push(active ? '1' : '0');
      }
      rows[d] = chars.join('');
    }
    return rows;
  }

  function formatSlotTime(slotIdx) {
    const h = Math.floor(slotIdx / 2);
    const m = (slotIdx % 2) * 30;
    return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
  }

  function updateSummaryAndHiddenInputs() {
    const rows = readRowsFromDom();
    let totalSlots = 0;
    for (let d = 0; d < 7; d++) {
      const input = document.getElementById('schedule-row-' + d);
      if (input) {
        input.value = rows[d];
      }
      for (let s = 0; s < 48; s++) {
        if (rows[d][s] === '1') totalSlots++;
      }
    }
    const totalHoursEl = document.getElementById('schedule-total-hours');
    if (totalHoursEl) {
      const hours = (totalSlots * 0.5).toFixed(1).replace(/\.0$/, '');
      totalHoursEl.textContent = hours;
    }
    renderDerivedRanges(rows);
  }

  function renderDerivedRanges(rows) {
    const container = document.getElementById('schedule-range-chips');
    if (!container) return;
    const chips = [];
    for (let d = 0; d < 7; d++) {
      let s = 0;
      while (s < 48) {
        if (rows[d][s] === '1') {
          const start = s;
          while (s < 48 && rows[d][s] === '1') s++;
          const end = s;
          chips.push({ day: d, start: start, end: end });
        } else {
          s++;
        }
      }
    }
    container.innerHTML = '';
    if (chips.length === 0) {
      const emptySpan = document.createElement('span');
      emptySpan.className = 'ogk-card-subtitle';
      emptySpan.textContent = 'Chưa có khung giờ nào được bật.';
      container.appendChild(emptySpan);
      return;
    }
    chips.slice(0, 14).forEach(function (item) {
      const chip = document.createElement('span');
      chip.className = 'range-chip';
      const label = DAY_LABELS[item.day] + ' ' + formatSlotTime(item.start) + '–' + formatSlotTime(item.end);
      const textNode = document.createElement('span');
      textNode.textContent = label;
      const removeBtn = document.createElement('button');
      removeBtn.type = 'button';
      removeBtn.className = 'btn btn-secondary btn-sm';
      removeBtn.textContent = '×';
      removeBtn.setAttribute('aria-label', 'Xóa khoảng ' + label);
      removeBtn.addEventListener('click', function () {
        setSlotsRange([item.day], item.start, item.end, false);
        updateSummaryAndHiddenInputs();
      });
      chip.appendChild(textNode);
      chip.appendChild(removeBtn);
      container.appendChild(chip);
    });
  }

  function setSlotsRange(days, startSlot, endSlot, allowed) {
    days.forEach(function (d) {
      for (let s = startSlot; s < endSlot; s++) {
        const btn = document.querySelector('button.slot[data-day="' + d + '"][data-slot="' + s + '"]');
        if (btn) {
          btn.setAttribute('aria-pressed', allowed ? 'true' : 'false');
          btn.textContent = allowed ? 'Mở' : 'Khóa';
        }
      }
    });
  }

  document.addEventListener('DOMContentLoaded', function () {
    const gridRoot = document.getElementById('schedule-matrix-root');
    if (!gridRoot) return;

    gridRoot.addEventListener('click', function (e) {
      const btn = e.target.closest('button.slot');
      if (!btn) return;
      const isPressed = btn.getAttribute('aria-pressed') === 'true';
      const nextState = !isPressed;
      btn.setAttribute('aria-pressed', nextState ? 'true' : 'false');
      btn.textContent = nextState ? 'Mở' : 'Khóa';
      updateSummaryAndHiddenInputs();
    });

    const addRangeBtn = document.getElementById('btn-add-schedule-range');
    if (addRangeBtn) {
      addRangeBtn.addEventListener('click', function () {
        const startSel = document.getElementById('range-start-slot');
        const endSel = document.getElementById('range-end-slot');
        const startSlot = parseInt(startSel ? startSel.value : '38', 10);
        const endSlot = parseInt(endSel ? endSel.value : '42', 10);
        if (endSlot <= startSlot) return;
        const checkedDays = [];
        document.querySelectorAll('input[name="range_day"]:checked').forEach(function (cb) {
          checkedDays.push(parseInt(cb.value, 10));
        });
        if (checkedDays.length === 0) return;
        setSlotsRange(checkedDays, startSlot, endSlot, true);
        updateSummaryAndHiddenInputs();
      });
    }

    const sameWeekendBtn = document.getElementById('btn-weekend-same');
    if (sameWeekendBtn) {
      sameWeekendBtn.addEventListener('click', function () {
        for (let s = 0; s < 48; s++) {
          const satBtn = document.querySelector('button.slot[data-day="5"][data-slot="' + s + '"]');
          const sunBtn = document.querySelector('button.slot[data-day="6"][data-slot="' + s + '"]');
          if (satBtn && sunBtn) {
            const state = satBtn.getAttribute('aria-pressed') === 'true';
            sunBtn.setAttribute('aria-pressed', state ? 'true' : 'false');
            sunBtn.textContent = state ? 'Mở' : 'Khóa';
          }
        }
        updateSummaryAndHiddenInputs();
      });
    }

    const clearAllBtn = document.getElementById('btn-clear-schedule');
    if (clearAllBtn) {
      clearAllBtn.addEventListener('click', function () {
        setSlotsRange([0, 1, 2, 3, 4, 5, 6], 0, 48, false);
        updateSummaryAndHiddenInputs();
      });
    }

    updateSummaryAndHiddenInputs();
  });
})();
