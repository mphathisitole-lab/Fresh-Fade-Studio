/* ===================================================================
   FreshFade Studio — Main JavaScript
   =================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    // --- Navbar scroll effect ---
    const navbar = document.querySelector(".navbar");
    if (navbar) {
        window.addEventListener("scroll", () => {
            navbar.classList.toggle("scrolled", window.scrollY > 50);
        });
    }

    // --- Mobile hamburger menu ---
    const hamburger = document.querySelector(".nav-hamburger");
    const navLinks = document.querySelector(".nav-links");
    if (hamburger && navLinks) {
        hamburger.addEventListener("click", () => {
            navLinks.classList.toggle("active");
            hamburger.classList.toggle("open");
        });
    }

    // --- Auto-dismiss flash messages ---
    document.querySelectorAll(".flash-msg").forEach(msg => {
        setTimeout(() => {
            msg.style.opacity = "0";
            msg.style.transform = "translateX(50px)";
            setTimeout(() => msg.remove(), 400);
        }, 5000);
    });

    document.querySelectorAll(".flash-close").forEach(btn => {
        btn.addEventListener("click", () => {
            const msg = btn.parentElement;
            msg.style.opacity = "0";
            msg.style.transform = "translateX(50px)";
            setTimeout(() => msg.remove(), 400);
        });
    });

    // --- Smooth scroll for anchor links ---
    document.querySelectorAll('a[href^="#"]').forEach(a => {
        a.addEventListener("click", e => {
            const target = document.querySelector(a.getAttribute("href"));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({ behavior: "smooth", block: "start" });
                if (navLinks) navLinks.classList.remove("active");
            }
        });
    });

    // --- Initialize booking calendar if on booking page ---
    if (document.getElementById("booking-calendar")) {
        initBookingCalendar();
    }
});


/* ===================================================================
   BOOKING CALENDAR
   =================================================================== */
let currentYear, currentMonth, selectedDate, selectedTime;

function initBookingCalendar() {
    const today = new Date();
    currentYear = today.getFullYear();
    currentMonth = today.getMonth() + 1;
    selectedDate = null;
    selectedTime = null;

    document.getElementById("prev-month").addEventListener("click", () => {
        currentMonth--;
        if (currentMonth < 1) { currentMonth = 12; currentYear--; }
        loadCalendar();
    });

    document.getElementById("next-month").addEventListener("click", () => {
        currentMonth++;
        if (currentMonth > 12) { currentMonth = 1; currentYear++; }
        loadCalendar();
    });

    loadCalendar();
}

async function loadCalendar() {
    const res = await fetch(`/api/calendar/${currentYear}/${currentMonth}`);
    const data = await res.json();

    document.getElementById("calendar-month-label").textContent =
        `${data.month_name} ${data.year}`;

    document.getElementById("calendar-work-hours").textContent =
        `Working Hours: ${data.work_hours} | ${data.slot_duration} per session`;

    const grid = document.getElementById("calendar-days");
    grid.innerHTML = "";

    // Day headers
    ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"].forEach(d => {
        const el = document.createElement("div");
        el.className = "cal-header";
        el.textContent = d;
        grid.appendChild(el);
    });

    // Offset for first day of month
    const firstDate = new Date(currentYear, currentMonth - 1, 1);
    let startDay = firstDate.getDay(); // 0=Sun
    startDay = startDay === 0 ? 6 : startDay - 1; // Convert to Mon=0

    for (let i = 0; i < startDay; i++) {
        const empty = document.createElement("div");
        empty.className = "cal-day empty";
        grid.appendChild(empty);
    }

    const todayStr = new Date().toISOString().split("T")[0];

    data.days.forEach(day => {
        const el = document.createElement("div");
        el.className = "cal-day";
        el.textContent = day.day;

        if (day.date === todayStr) el.classList.add("today");
        if (day.is_past) el.classList.add("past");
        if (day.closed) {
            el.classList.add("closed-day");
        }

        // Availability dot
        if (!day.closed && !day.is_past) {
            const dot = document.createElement("div");
            dot.className = "availability-dot";
            if (day.available === day.total_slots) {
                dot.style.background = "var(--accent-green)";
            } else if (day.available > 0) {
                dot.style.background = "var(--gold)";
            } else {
                dot.style.background = "var(--accent-red)";
            }
            el.appendChild(dot);

            el.addEventListener("click", () => selectDate(day.date, el));
        }

        if (selectedDate === day.date) el.classList.add("selected");
        grid.appendChild(el);
    });
}

function selectDate(dateStr, el) {
    selectedDate = dateStr;
    selectedTime = null;
    document.getElementById("selected-date").value = dateStr;
    document.getElementById("selected-time").value = "";

    document.querySelectorAll(".cal-day").forEach(d => d.classList.remove("selected"));
    el.classList.add("selected");

    loadSlots(dateStr);
}

async function loadSlots(dateStr) {
    const panel = document.getElementById("slots-container");
    panel.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem;">Loading slots...</p>';

    const res = await fetch(`/api/slots/${dateStr}`);
    const data = await res.json();

    if (data.message) {
        panel.innerHTML = `<p style="color:var(--text-muted);text-align:center;padding:2rem;">${data.message}</p>`;
        return;
    }

    if (data.slots.length === 0) {
        panel.innerHTML = '<p style="color:var(--text-muted);text-align:center;padding:2rem;">No available slots for this day.</p>';
        return;
    }

    const grid = document.createElement("div");
    grid.className = "slots-grid";

    data.slots.forEach(slot => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "slot-btn";
        btn.textContent = slot.time;

        if (!slot.available) {
            btn.classList.add("booked");
            btn.title = slot.blocked ? "Blocked by barber" : "Already booked";
            if (slot.blocked) {
                btn.textContent = slot.time + " 🚫";
            }
        } else {
            btn.addEventListener("click", () => selectTimeSlot(slot.time, btn));
        }

        if (selectedTime === slot.time) btn.classList.add("selected");
        grid.appendChild(btn);
    });

    panel.innerHTML = "";
    panel.appendChild(grid);

    // Show available count
    const avail = data.slots.filter(s => s.available).length;
    const total = data.slots.length;
    const info = document.createElement("p");
    info.style.cssText = "font-size:0.8rem;color:var(--text-muted);text-align:center;margin-top:0.8rem;";
    info.textContent = `${avail} of ${total} slots available`;
    panel.appendChild(info);
}

function selectTimeSlot(timeStr, btn) {
    selectedTime = timeStr;
    document.getElementById("selected-time").value = timeStr;

    document.querySelectorAll(".slot-btn").forEach(b => b.classList.remove("selected"));
    btn.classList.add("selected");

    updateBookingSummary();
}

function updateBookingSummary() {
    const summary = document.getElementById("booking-summary");
    if (!summary) return;

    const styleSelect = document.getElementById("hairstyle-select");
    const styleName = styleSelect?.options[styleSelect.selectedIndex]?.text || "—";
    const price = styleSelect?.options[styleSelect.selectedIndex]?.dataset.price || "—";

    const dateFormatted = selectedDate
        ? new Date(selectedDate + "T00:00:00").toLocaleDateString("en-ZA", {
            weekday: "long", year: "numeric", month: "long", day: "numeric"
          })
        : "—";

    document.getElementById("summary-style").textContent = styleName;
    document.getElementById("summary-date").textContent = dateFormatted;
    document.getElementById("summary-time").textContent = selectedTime || "—";
    document.getElementById("summary-price").textContent = price !== "—" ? `R${price}` : "—";

    summary.style.display = "block";
}

/* ===================================================================
   BOOKING FORM VALIDATION
   =================================================================== */
function validateBookingForm() {
    const style = document.getElementById("hairstyle-select")?.value;
    const dateVal = document.getElementById("selected-date")?.value;
    const timeVal = document.getElementById("selected-time")?.value;
    const payment = document.querySelector('input[name="payment_method"]:checked');

    if (!style) { alert("Please select a hairstyle."); return false; }
    if (!dateVal) { alert("Please select a date from the calendar."); return false; }
    if (!timeVal) { alert("Please select a time slot."); return false; }
    if (!payment) { alert("Please choose a payment method."); return false; }
    return true;
}

/* ===================================================================
   HAIRSTYLE SELECT — update price & summary
   =================================================================== */
function onHairstyleChange(select) {
    const opt = select.options[select.selectedIndex];
    const price = opt.dataset.price;
    const priceDisplay = document.getElementById("style-price-display");
    if (priceDisplay) {
        priceDisplay.textContent = price ? `R${price}` : "";
    }
    updateBookingSummary();
}
