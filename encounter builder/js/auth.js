function renderSignInGate() {
  if (document.getElementById('auth-gate')) return;
  const overlay = document.createElement('div');
  overlay.id = 'auth-gate';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:9999;background:#f5f1e8;display:flex;align-items:center;justify-content:center;font-family:Georgia,serif;';
  overlay.innerHTML = `
    <div style="background:#fffdf7;border:1px solid #d6c9ad;border-radius:6px;padding:2rem 2.5rem;max-width:360px;width:100%;text-align:center;">
      <h2 style="margin:0 0 0.5rem;font-size:20px;color:#6b1a1a;">Sign in</h2>
      <p style="margin:0 0 1.25rem;font-size:13px;color:#6b5d4a;">Enter your email and we'll send you a sign-in link.</p>
      <input id="auth-email" type="email" placeholder="you@example.com"
        style="width:100%;padding:8px 10px;border:1px solid #d6c9ad;border-radius:3px;font-size:14px;margin-bottom:10px;box-sizing:border-box;" />
      <button id="auth-send"
        style="width:100%;padding:8px 10px;background:#6b1a1a;color:#fff;border:none;border-radius:3px;font-size:14px;cursor:pointer;">
        Send magic link
      </button>
      <p id="auth-status" style="margin:12px 0 0;font-size:12px;color:#6b5d4a;min-height:1em;"></p>
    </div>`;
  document.body.appendChild(overlay);

  document.getElementById('auth-send').addEventListener('click', async () => {
    const email = document.getElementById('auth-email').value.trim();
    const status = document.getElementById('auth-status');
    if (!email) { status.textContent = 'Enter an email address.'; return; }
    status.textContent = 'Sending...';
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.href },
    });
    status.textContent = error ? error.message : 'Check your email for the link.';
  });
}

async function requireAuth() {
  const { data: { session } } = await supabase.auth.getSession();
  if (session) return session.user;
  renderSignInGate();
  return new Promise(() => {});
}
