/**
 * College Mess Management System - Interactive Frontend Logic
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Mobile Sidebar Toggle
  const toggleBtn = document.getElementById('mobileMenuToggle');
  const sidebar = document.getElementById('appSidebar');

  if (toggleBtn && sidebar) {
    toggleBtn.addEventListener('click', function () {
      sidebar.classList.toggle('mobile-open');
    });

    // Close on outside click on mobile
    document.addEventListener('click', function (e) {
      if (window.innerWidth <= 768) {
        if (!sidebar.contains(e.target) && !toggleBtn.contains(e.target) && sidebar.classList.contains('mobile-open')) {
          sidebar.classList.remove('mobile-open');
        }
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
