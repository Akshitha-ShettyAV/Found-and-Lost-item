"use strict";

const STORAGE_KEY = "campus-connect-students";
const REMEMBER_KEY = "campus-connect-remembered-email";
const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const INDIAN_PHONE_PATTERN = /^(?:\+91)?[6-9]\d{9}$/;

const welcomeView = document.querySelector("#welcome-view");
const authCard = document.querySelector(".auth-card");
const loginView = document.querySelector("#login-view");
const registerView = document.querySelector("#register-view");
const loginForm = document.querySelector("#login-form");
const registerForm = document.querySelector("#register-form");
const loginMessage = document.querySelector("#login-message");
const registerMessage = document.querySelector("#register-message");
const emailInput = document.querySelector("#register-email");
const studentIdInput = document.querySelector("#student-id");
const passwordInput = document.querySelector("#register-password");
const confirmPasswordInput = document.querySelector("#confirm-password");
const loginEmailInput = document.querySelector("#login-email");
const loginPasswordInput = document.querySelector("#login-password");
const rememberCheckbox = document.querySelector("#remember-me");

document.querySelector("#current-year").textContent = String(new Date().getFullYear());

function showView(viewName) {
  const showWelcome = viewName === "welcome";
  const showLogin = viewName === "login";
  welcomeView.hidden = !showWelcome;
  authCard.hidden = showWelcome;
  loginView.hidden = !showLogin;
  registerView.hidden = showLogin || showWelcome;
  loginView.classList.toggle("is-hidden", !showLogin);
  registerView.classList.toggle("is-hidden", showLogin || showWelcome);
  clearMessage(loginMessage);
  clearMessage(registerMessage);

  const focusTarget = showWelcome
    ? welcomeView.querySelector('[data-view="register"]')
    : (showLogin ? loginView : registerView).querySelector("input, select");
  if (focusTarget) focusTarget.focus({ preventScroll: true });
}

document.querySelectorAll("[data-view]").forEach((button) => {
  button.addEventListener("click", (event) => {
    event.preventDefault();
    showView(button.dataset.view);
  });
});

document.querySelectorAll("[data-password-target]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById(button.dataset.passwordTarget);
    const shouldShow = input.type === "password";
    input.type = shouldShow ? "text" : "password";
    button.setAttribute("aria-label", shouldShow ? "Hide password" : "Show password");
    button.setAttribute("aria-pressed", String(shouldShow));
  });
});

function showMessage(element, message, type) {
  element.textContent = message;
  element.className = `form-message is-visible is-${type}`;
}

function clearMessage(element) {
  element.textContent = "";
  element.className = "form-message";
}

function markInvalid(input, invalid) {
  if (invalid) input.setAttribute("aria-invalid", "true");
  else input.removeAttribute("aria-invalid");
}

function clearInvalid(form) {
  form.querySelectorAll("[aria-invalid]").forEach((input) => input.removeAttribute("aria-invalid"));
}

function readStudents() {
  try {
    const stored = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    if (!Array.isArray(stored)) throw new Error("Stored student data is not a list.");
    return stored;
  } catch (error) {
    console.error("Could not read saved student accounts.", error);
    throw new Error("Saved account data could not be read. Please clear this site's stored data and try again.");
  }
}

function saveStudents(students) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(students));
  } catch (error) {
    console.error("Could not save student account.", error);
    throw new Error("Your account could not be saved in this browser. Check available storage and try again.");
  }
}

async function hashPassword(password, salt) {
  if (!globalThis.crypto || !globalThis.crypto.subtle) {
    throw new Error("Secure password hashing is unavailable in this browser. Open the project on localhost or in a modern browser.");
  }
  const bytes = new TextEncoder().encode(`${salt}:${password}`);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function clearInputErrors(inputs) {
  inputs.forEach((input) => markInvalid(input, false));
}

registerForm.addEventListener("input", () => {
  clearMessage(registerMessage);
  clearInputErrors([emailInput, studentIdInput, passwordInput, confirmPasswordInput]);
});

registerForm.addEventListener("change", () => clearMessage(registerMessage));
loginForm.addEventListener("input", () => {
  clearMessage(loginMessage);
  clearInputErrors([loginEmailInput, loginPasswordInput]);
});

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(registerMessage);
  clearInvalid(registerForm);

  if (!registerForm.reportValidity()) return;

  const formData = new FormData(registerForm);
  const fullName = String(formData.get("fullName")).trim();
  const studentId = String(formData.get("studentId")).trim();
  const email = String(formData.get("email")).trim().toLowerCase();
  const phone = String(formData.get("phone")).trim();
  const normalizedPhone = phone.replace(/[\s()-]/g, "");
  const department = String(formData.get("department"));
  const studyYear = String(formData.get("studyYear"));
  const password = String(formData.get("password"));
  const confirmPassword = String(formData.get("confirmPassword"));

  if (!EMAIL_PATTERN.test(email)) {
    markInvalid(emailInput, true);
    showMessage(registerMessage, "Enter a valid email address.", "error");
    emailInput.focus();
    return;
  }
  if (!INDIAN_PHONE_PATTERN.test(normalizedPhone)) {
    const phoneInput = document.querySelector("#phone");
    markInvalid(phoneInput, true);
    showMessage(registerMessage, "Enter a valid Indian mobile number: 10 digits starting with 6–9, optionally with +91.", "error");
    phoneInput.focus();
    return;
  }
  if (password.length < 8) {
    markInvalid(passwordInput, true);
    showMessage(registerMessage, "Your password must be at least 8 characters long.", "error");
    passwordInput.focus();
    return;
  }
  if (password !== confirmPassword) {
    markInvalid(confirmPasswordInput, true);
    showMessage(registerMessage, "Those passwords do not match. Please try again.", "error");
    confirmPasswordInput.focus();
    return;
  }

  try {
    const students = readStudents();
    const emailExists = students.some((student) => student.email === email);
    const idExists = students.some((student) => student.studentId.toLowerCase() === studentId.toLowerCase());

    if (emailExists || idExists) {
      if (emailExists) markInvalid(emailInput, true);
      if (idExists) markInvalid(studentIdInput, true);
      const duplicate = emailExists && idExists
        ? "That email and student ID are already registered."
        : emailExists
          ? "An account with that email address already exists."
          : "That student ID is already registered.";
      showMessage(registerMessage, duplicate, "error");
      (emailExists ? emailInput : studentIdInput).focus();
      return;
    }

    const salt = crypto.randomUUID();
    const passwordHash = await hashPassword(password, salt);
    students.push({
      fullName,
      studentId,
      email,
      phone: normalizedPhone.startsWith("+91") ? normalizedPhone : `+91${normalizedPhone}`,
      department,
      studyYear,
      salt,
      passwordHash
    });
    saveStudents(students);
    registerForm.reset();
    showView("login");
    loginEmailInput.value = email;
    showMessage(loginMessage, "Your account is ready. Sign in with your new credentials.", "success");
  } catch (error) {
    showMessage(registerMessage, error.message || "We couldn't create your account. Please try again.", "error");
  }
});

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearMessage(loginMessage);
  clearInvalid(loginForm);

  if (!loginForm.reportValidity()) return;

  const email = loginEmailInput.value.trim().toLowerCase();
  const password = loginPasswordInput.value;
  if (!EMAIL_PATTERN.test(email)) {
    markInvalid(loginEmailInput, true);
    showMessage(loginMessage, "Enter a valid email address.", "error");
    loginEmailInput.focus();
    return;
  }

  try {
    const student = readStudents().find((account) => account.email === email);
    const enteredHash = student
      ? await hashPassword(password, student.salt)
      : "";

    if (!student || enteredHash !== student.passwordHash) {
      markInvalid(loginEmailInput, true);
      markInvalid(loginPasswordInput, true);
      showMessage(loginMessage, "Email or password is incorrect. Check your details or create an account.", "error");
      return;
    }

    if (rememberCheckbox.checked) localStorage.setItem(REMEMBER_KEY, email);
    else localStorage.removeItem(REMEMBER_KEY);
    showMessage(loginMessage, `Welcome back, ${student.fullName}! You're signed in.`, "success");
    loginPasswordInput.value = "";
  } catch (error) {
    showMessage(loginMessage, error.message || "We couldn't sign you in. Please try again.", "error");
  }
});

document.querySelector("#forgot-password").addEventListener("click", () => {
  clearMessage(loginMessage);
  showMessage(loginMessage, "Password reset isn't available in this demo. Please contact your campus administrator.", "error");
});

try {
  const rememberedEmail = localStorage.getItem(REMEMBER_KEY);
  if (rememberedEmail) {
    loginEmailInput.value = rememberedEmail;
    rememberCheckbox.checked = true;
  }
} catch (error) {
  console.error("Could not load remembered email preference.", error);
}
