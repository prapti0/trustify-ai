import { useEffect, useState, type FormEvent } from "react";
import { changePassword, deleteAccount, deleteAllFiles, errorMessage, listSessions, revokeSession, updateProfile } from "../api/client";
import type { SessionInfo } from "../api/types";
import { AppShell } from "../components/Shell";
import { Button, Dialog, TextField } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { formatWhen } from "../lib/format";
import { useNavigate } from "react-router-dom";

export function SettingsPage() {
  const { session, setSession, clear } = useAuth();
  const { theme, toggle } = useTheme();
  const { push } = useToast();
  const navigate = useNavigate();
  const [name, setName] = useState(session?.user.full_name ?? "");
  const [email, setEmail] = useState(session?.user.email ?? "");
  const [currentPassword, setCurrentPassword] = useState("");
  const [nextPassword, setNextPassword] = useState("");
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [confirmDelete, setConfirmDelete] = useState<"files" | "account" | null>(null);
  const [browserNotes, setBrowserNotes] = useState(() => localStorage.getItem("trustify.notes") !== "off");

  useEffect(() => {
    listSessions().then(setSessions).catch(() => setSessions([]));
  }, []);

  async function saveProfile(event: FormEvent) {
    event.preventDefault();
    try {
      const user = await updateProfile({ full_name: name, email });
      if (session) setSession({ access_token: session.accessToken, token_type: "bearer", session_id: session.sessionId, user });
      push("Profile saved.");
    } catch (error) {
      push(errorMessage(error, "Profile could not be saved."), "danger");
    }
  }

  async function savePassword(event: FormEvent) {
    event.preventDefault();
    try {
      await changePassword({ current_password: currentPassword, new_password: nextPassword });
      setCurrentPassword("");
      setNextPassword("");
      push("Password updated.");
    } catch (error) {
      push(errorMessage(error, "Password could not be changed."), "danger");
    }
  }

  return (
    <AppShell title="Settings" subtitle="Profile, security, and browser preferences for this account.">
      <div className="grid max-w-3xl gap-6">
        <form onSubmit={saveProfile} className="card grid gap-4 p-5">
          <h2 className="font-medium">Profile Settings</h2>
          <TextField label="Full Name" name="full_name" required value={name} onChange={(event) => setName(event.target.value)} />
          <TextField label="Email" name="email" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          <p className="text-sm muted">Profile pictures are not stored.</p>
          <Button type="submit">Save profile</Button>
        </form>
        <form onSubmit={savePassword} className="card grid gap-4 p-5">
          <h2 className="font-medium">Security</h2>
          <TextField label="Change Password" name="current_password" type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
          <TextField label="New Password" name="new_password" type="password" autoComplete="new-password" minLength={12} required value={nextPassword} onChange={(event) => setNextPassword(event.target.value)} />
          <Button type="submit">Update password</Button>
          <h3 className="font-medium">Active Sessions</h3>
          <ul className="divide-y divide-[var(--line)] text-sm">
            {sessions.map((item) => (
              <li key={item.id} className="flex flex-wrap items-center gap-3 py-3">
                <span>{formatWhen(item.created_at)}</span>
                <span className="muted">{item.ip_address ?? "unknown address"}</span>
                <span className="muted">{item.revoked_at ? "revoked" : item.current ? "this browser" : "active"}</span>
                {!item.revoked_at ? (
                  <button type="button" className="text-[var(--blue)]" onClick={() => void revokeSession(item.id).then(() => listSessions().then(setSessions))}>Revoke</button>
                ) : null}
              </li>
            ))}
          </ul>
          <p className="text-sm muted">Two-factor authentication is not available.</p>
        </form>
        <section className="card grid gap-3 p-5">
          <h2 className="font-medium">Preferences</h2>
          <button type="button" className="btn btn-secondary w-fit" onClick={toggle}>Theme: {theme === "dark" ? "Dark" : "Light"}</button>
          <label className="label" htmlFor="language">Language</label>
          <select id="language" className="field" disabled value="en">
            <option value="en">English</option>
          </select>
          <p className="text-xs muted">Other languages are not available.</p>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={browserNotes}
              onChange={(event) => {
                setBrowserNotes(event.target.checked);
                localStorage.setItem("trustify.notes", event.target.checked ? "on" : "off");
              }}
            />
            Keep interface notices in this browser
          </label>
          <p className="text-xs muted">Notification preferences are stored in this browser. Email notifications are not sent.</p>
        </section>
        <section className="card grid gap-3 p-5">
          <h2 className="font-medium">Privacy</h2>
          <p className="text-sm muted">Uploaded files stay until you delete them. No automatic retention schedule is configured.</p>
          <button type="button" className="btn btn-secondary w-fit" onClick={() => setConfirmDelete("files")}>Delete Uploaded Files</button>
          <button type="button" className="btn btn-secondary w-fit" onClick={() => setConfirmDelete("account")}>Delete Account</button>
          <a className="text-sm text-[var(--blue)]" href="/privacy">Privacy Policy</a>
        </section>
      </div>
      {confirmDelete ? (
        <Dialog
          title={confirmDelete === "files" ? "Delete Uploaded Files" : "Delete Account"}
          body={confirmDelete === "files" ? "Delete every file and report in this account?" : "Delete the account, its sessions, and its files?"}
          confirmLabel={confirmDelete === "files" ? "Delete files" : "Delete account"}
          onCancel={() => setConfirmDelete(null)}
          onConfirm={() => {
            const action = confirmDelete === "files" ? deleteAllFiles : deleteAccount;
            void action()
              .then(() => {
                if (confirmDelete === "account") {
                  clear();
                  navigate("/");
                  return;
                }
                push("Uploaded files were deleted.");
                setConfirmDelete(null);
              })
              .catch((error) => push(errorMessage(error, "The deletion could not be completed."), "danger"));
          }}
        />
      ) : null}
    </AppShell>
  );
}
