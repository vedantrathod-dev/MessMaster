/**
 * College Mess Management System - Interactive Frontend Logic
 */

document.addEventListener('DOMContentLoaded', function () {
  // 0. Dark / Light Theme Toggle System
  const themeToggleBtn = document.getElementById('themeToggleBtn');
  const themeToggleIcon = document.getElementById('themeToggleIcon');

  function updateThemeUI(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('messmaster_theme', theme);
    if (themeToggleIcon) {
      themeToggleIcon.textContent = theme === 'light' ? '☀️' : '🌙';
    }
  }

  // Sync icon with currently active theme
  const initialTheme = document.documentElement.getAttribute('data-theme') || localStorage.getItem('messmaster_theme') || 'dark';
  updateThemeUI(initialTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener('click', function () {
      const activeTheme = document.documentElement.getAttribute('data-theme') || 'dark';
      const nextTheme = activeTheme === 'dark' ? 'light' : 'dark';
      updateThemeUI(nextTheme);
    });
  }

  // Keyboard shortcut: ⌘ + Space or Ctrl + Space focuses Search
  const searchInput = document.getElementById('globalSearchInput');
  document.addEventListener('keydown', function (e) {
    if ((e.metaKey || e.ctrlKey) && e.code === 'Space') {
      e.preventDefault();
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
    }
  });

  if (searchInput) {
    searchInput.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') {
        const query = searchInput.value.trim();
        if (query) {
          window.location.href = `/students?search=${encodeURIComponent(query)}`;
        }
      }
    });
  }

  // 1. Mobile Sidebar & Backdrop Toggle
  const toggleBtn = document.getElementById('mobileMenuToggle');
  const closeBtn = document.getElementById('sidebarCloseBtn');
  const sidebar = document.getElementById('appSidebar');
  const backdrop = document.getElementById('sidebarBackdrop');

  function openSidebar() {
    if (sidebar) sidebar.classList.add('mobile-open');
    if (backdrop) backdrop.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeSidebar() {
    if (sidebar) sidebar.classList.remove('mobile-open');
    if (backdrop) backdrop.classList.remove('active');
    document.body.style.overflow = '';
  }

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (sidebar.classList.contains('mobile-open')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    });

    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);

    // Close when clicking nav items on mobile
    sidebar.querySelectorAll('.nav-item').forEach(function (item) {
      item.addEventListener('click', function () {
        if (window.innerWidth <= 1024) {
          closeSidebar();
        }
      });
    });

    // Close on Escape key
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        closeSidebar();
        document.querySelectorAll('.modal-overlay.active').forEach(function (modal) {
          modal.classList.remove('active');
        });
      }
    });
  }

  // 2. Auto-Dismiss Flash Alerts after 5 seconds
  const flashAlerts = document.querySelectorAll('.alert');
  flashAlerts.forEach(function (alert) {
    setTimeout(function () {
      alert.style.transition = 'opacity 0.4s ease';
      alert.style.opacity = '0';
      setTimeout(function () {
        if (alert.parentNode) {
          alert.parentNode.removeChild(alert);
        }
      }, 400);
    }, 6000);
  });

  // 3. Admission & Renewal Dynamic Calculations
  const durationInput = document.getElementById('planDuration');
  const startDateInput = document.getElementById('messStartDate');
  const totalFeeInput = document.getElementById('totalFee');
  const amountPaidInput = document.getElementById('amountPaid');
  const messTypeSelect = document.getElementById('messType');
  const balancePreview = document.getElementById('balancePreview');
  const expiryPreview = document.getElementById('expiryPreview');

  function calculateExpiryAndBalance() {
    // Expiry date calculation
    if (startDateInput && durationInput && expiryPreview) {
      const startVal = startDateInput.value;
      const durationVal = parseInt(durationInput.value, 10);

      if (startVal && !isNaN(durationVal)) {
        const start = new Date(startVal);
        start.setDate(start.getDate() + durationVal);
        const yyyy = start.getFullYear();
        const mm = String(start.getMonth() + 1).padStart(2, '0');
        const dd = String(start.getDate()).padStart(2, '0');
        expiryPreview.textContent = `${yyyy}-${mm}-${dd}`;
      }
    }

    // Balance calculation
    if (totalFeeInput && amountPaidInput && balancePreview) {
      const total = parseFloat(totalFeeInput.value) || 0;
      const paid = parseFloat(amountPaidInput.value) || 0;
      const balance = Math.max(0, total - paid);
      balancePreview.textContent = balance.toFixed(2);

      // Warning color if negative or overpaid
      if (paid > total) {
        amountPaidInput.style.borderColor = 'var(--danger)';
      } else {
        amountPaidInput.style.borderColor = 'var(--input-border)';
      }
    }
  }

  if (durationInput) durationInput.addEventListener('input', calculateExpiryAndBalance);
  if (startDateInput) startDateInput.addEventListener('change', calculateExpiryAndBalance);
  if (totalFeeInput) totalFeeInput.addEventListener('input', calculateExpiryAndBalance);
  if (amountPaidInput) amountPaidInput.addEventListener('input', calculateExpiryAndBalance);

  // Auto fee adjustment on Mess Type change if fee input hasn't been manually overridden
  if (messTypeSelect && totalFeeInput) {
    messTypeSelect.addEventListener('change', function () {
      const vegDefault = parseFloat(document.getElementById('vegDefaultFee')?.value || 3200);
      const nonvegDefault = parseFloat(document.getElementById('nonvegDefaultFee')?.value || 4200);
      const duration = parseInt(durationInput?.value || 30, 10);
      const ratio = duration / 30;

      if (messTypeSelect.value === 'Veg') {
        totalFeeInput.value = (vegDefault * ratio).toFixed(2);
      } else {
        totalFeeInput.value = (nonvegDefault * ratio).toFixed(2);
      }
      calculateExpiryAndBalance();
    });
  }

  // Initial calculation on page load
  calculateExpiryAndBalance();

  // 4. Modal Open & Close System
  window.openModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.add('active');
    }
  };

  window.closeModal = function (modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
      modal.classList.remove('active');
    }
  };

  // Close modals when clicking backdrop
  document.querySelectorAll('.modal-overlay').forEach(function (overlay) {
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) {
        overlay.classList.remove('active');
      }
    });
  });

  // 5. Quick Record Payment Modal Populator
  window.populatePaymentModal = function (studentId, studentName, balance) {
    const sIdInput = document.getElementById('modalStudentId');
    const sNameDisplay = document.getElementById('modalStudentName');
    const balanceDisplay = document.getElementById('modalBalance');
    const amountInput = document.getElementById('modalAmount');

    if (sIdInput) sIdInput.value = studentId;
    if (sNameDisplay) sNameDisplay.textContent = studentName + ` (${studentId})`;
    if (balanceDisplay) balanceDisplay.textContent = parseFloat(balance).toFixed(2);
    if (amountInput) {
      amountInput.value = balance > 0 ? balance : '';
      amountInput.max = balance;
    }

    openModal('paymentModal');
  };

  // 6. Quick Renew Mess Modal Populator
  window.populateRenewModal = function (studentId, studentName, messType) {
    const sIdInput = document.getElementById('renewStudentId');
    const sNameDisplay = document.getElementById('renewStudentName');
    const typeSelect = document.getElementById('renewMessType');

    if (sIdInput) sIdInput.value = studentId;
    if (sNameDisplay) sNameDisplay.textContent = studentName + ` (${studentId})`;
    if (typeSelect) typeSelect.value = messType;

    openModal('renewModal');
  };

  // 7. Bulk Mark Attendance Helpers
  const markAllPresentBtn = document.getElementById('btnMarkAllPresent');
  const markAllAbsentBtn = document.getElementById('btnMarkAllAbsent');

  if (markAllPresentBtn) {
    markAllPresentBtn.addEventListener('click', function () {
      document.querySelectorAll("input[type='radio'][value='Present']").forEach(function (radio) {
        radio.checked = true;
      });
    });
  }

  if (markAllAbsentBtn) {
    markAllAbsentBtn.addEventListener('click', function () {
      document.querySelectorAll("input[type='radio'][value='Absent']").forEach(function (radio) {
        radio.checked = true;
      });
    });
  }
});

// Print trigger function
function printReceipt() {
  window.print();
}
