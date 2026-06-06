import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Download, ExternalLink, ShieldAlert } from "lucide-react";
import { Button } from "../components/ui/button";
import { toast } from "sonner";
import client, { getSession, API } from "../lib/api";
import Header from "../components/Header";

const formatDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

export default function EvidenceVault() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getSession()) {
      navigate("/");
      return;
    }
    (async () => {
      try {
        const res = await client.get("/evidence");
        setItems(res.data);
      } catch (err) {
        toast.error(err?.response?.data?.detail || "Failed to load evidence");
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);

  const downloadEvidence = async (id) => {
    try {
      const email = getSession();
      const r = await fetch(`${API}/evidence/${id}/download`, {
        headers: { "X-User-Email": email },
      });
      if (!r.ok) throw new Error("Download failed");
      const blob = await r.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `evidence-${id}.jpg`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      toast.error("Could not download evidence");
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-6xl mx-auto px-6 lg:px-10 py-12" data-testid="evidence-page">
        <p className="text-xs uppercase tracking-widest text-primary flex items-center gap-2">
          <span className="brand-accent-dot" /> Evidence Vault
        </p>
        <h1 className="mt-3 font-heading text-3xl sm:text-4xl font-semibold tracking-tight">
          Saved evidence
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Screenshots and metadata for every flagged copy. Use these when filing a report with Etsy.
        </p>

        {loading ? (
          <div className="p-10 text-center text-sm text-muted-foreground">
            <Loader2 className="w-5 h-5 animate-spin inline mr-2" />
            Loading evidence...
          </div>
        ) : items.length === 0 ? (
          <div
            className="mt-12 border border-border rounded-sm p-16 text-center bg-background"
            data-testid="evidence-empty-state"
          >
            <ShieldAlert className="w-8 h-8 text-primary mx-auto" />
            <p className="mt-4 font-heading text-lg font-semibold">No evidence yet</p>
            <p className="mt-2 text-sm text-muted-foreground max-w-md mx-auto">
              When we detect a copy of one of your listings, the screenshot and details will appear here.
            </p>
          </div>
        ) : (
          <div className="mt-10 grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {items.map((ev) => (
              <article
                key={ev.id}
                data-testid={`evidence-card-${ev.id}`}
                className="border border-border rounded-sm bg-background overflow-hidden flex flex-col"
              >
                <div className="aspect-[4/3] bg-secondary border-b border-border overflow-hidden">
                  <img
                    src={ev.screenshot_url}
                    alt="evidence"
                    className="w-full h-full object-cover"
                  />
                </div>
                <div className="p-5 flex-1 flex flex-col">
                  <div className="flex items-center justify-between text-xs">
                    <span className="px-2 py-1 rounded-sm bg-red-100 text-red-800 border border-red-200">
                      {Math.round(ev.similarity * 100)}% match
                    </span>
                    <span className="text-muted-foreground">{formatDate(ev.detected_at)}</span>
                  </div>
                  <p className="mt-4 text-sm font-medium line-clamp-2">{ev.suspicious_title}</p>
                  {ev.suspicious_shop && (
                    <p className="mt-1 text-xs text-muted-foreground">
                      Shop: <span className="font-medium text-foreground">{ev.suspicious_shop}</span>
                    </p>
                  )}
                  <p className="mt-3 text-xs text-muted-foreground">
                    vs your listing: <span className="text-foreground">{ev.original_title}</span>
                  </p>
                  <div className="mt-auto pt-5 flex items-center gap-2">
                    <a
                      href={ev.suspicious_url}
                      target="_blank"
                      rel="noreferrer"
                      data-testid={`evidence-open-${ev.id}`}
                      className="flex-1"
                    >
                      <Button
                        variant="outline"
                        size="sm"
                        className="w-full rounded-sm border-border"
                      >
                        <ExternalLink className="w-3.5 h-3.5 mr-1.5" />
                        View
                      </Button>
                    </a>
                    <Button
                      size="sm"
                      onClick={() => downloadEvidence(ev.id)}
                      data-testid={`evidence-download-${ev.id}`}
                      className="rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
                    >
                      <Download className="w-3.5 h-3.5 mr-1.5" />
                      Download
                    </Button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
