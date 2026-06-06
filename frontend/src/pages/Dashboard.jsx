import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, RefreshCw, Trash2, Plus, ExternalLink } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui/table";
import { toast } from "sonner";
import client, { getSession } from "../lib/api";
import Header from "../components/Header";

const StatusBadge = ({ status }) => {
  const styles = {
    Watching: "bg-[#2D9B6F]/10 text-[#2D9B6F] border-[#2D9B6F]/20",
    "Price Changed": "bg-yellow-100 text-yellow-800 border-yellow-200",
    "Copy Detected": "bg-red-100 text-red-800 border-red-200",
  };
  const cls = styles[status] || styles.Watching;
  return (
    <span
      data-testid={`status-badge-${status.replaceAll(" ", "-").toLowerCase()}`}
      className={`inline-flex items-center px-2 py-1 text-xs font-medium border rounded-sm ${cls}`}
    >
      {status}
    </span>
  );
};

const formatDate = (iso) => {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
};

export default function Dashboard() {
  const navigate = useNavigate();
  const [listings, setListings] = useState([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (!getSession()) {
      navigate("/");
      return;
    }
    fetchListings();
  }, [navigate]);

  const fetchListings = async () => {
    setLoading(true);
    try {
      const res = await client.get("/listings");
      setListings(res.data);
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to load listings");
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    setAdding(true);
    try {
      await client.post("/listings", { url: url.trim() });
      setUrl("");
      toast.success("Listing added. We'll watch it for you.");
      await fetchListings();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Failed to add listing");
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await client.delete(`/listings/${id}`);
      toast.success("Listing removed");
      setListings((prev) => prev.filter((l) => l.id !== id));
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Delete failed");
    }
  };

  const handleCheckNow = async () => {
    setChecking(true);
    try {
      const res = await client.post("/listings/check-now");
      toast.success(`Checked ${res.data.checked} listings`);
      await fetchListings();
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Check failed");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-6xl mx-auto px-6 lg:px-10 py-12" data-testid="dashboard-page">
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-widest text-primary flex items-center gap-2">
              <span className="brand-accent-dot" /> Dashboard
            </p>
            <h1 className="mt-3 font-heading text-3xl sm:text-4xl font-semibold tracking-tight">
              Your protected listings
            </h1>
            <p className="mt-2 text-sm text-muted-foreground">
              We check every 24 hours. You can trigger an instant check anytime.
            </p>
          </div>
          <Button
            onClick={handleCheckNow}
            disabled={checking || listings.length === 0}
            data-testid="check-now-btn"
            className="rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {checking ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Check Now
          </Button>
        </div>

        <form
          onSubmit={handleAdd}
          data-testid="add-listing-form"
          className="mt-10 flex flex-col sm:flex-row gap-3"
        >
          <Input
            placeholder="Paste your Etsy listing URL to monitor (e.g. https://www.etsy.com/listing/123456789/...)"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            data-testid="listing-url-input"
            className="h-12 rounded-sm border-border bg-background flex-1"
          />
          <Button
            type="submit"
            disabled={adding}
            data-testid="add-listing-btn"
            className="h-12 px-6 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
          >
            {adding ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
            Add
          </Button>
        </form>

        <div className="mt-10 border border-border rounded-sm bg-background overflow-hidden">
          {loading ? (
            <div className="p-10 text-center text-sm text-muted-foreground">
              <Loader2 className="w-5 h-5 animate-spin inline mr-2" />
              Loading listings...
            </div>
          ) : listings.length === 0 ? (
            <div className="p-16 text-center" data-testid="empty-state">
              <p className="font-heading text-lg font-semibold">No listings yet</p>
              <p className="mt-2 text-sm text-muted-foreground">
                Paste an Etsy listing URL above to start monitoring.
              </p>
            </div>
          ) : (
            <Table data-testid="listings-table">
              <TableHeader>
                <TableRow className="bg-secondary/50 hover:bg-secondary/50">
                  <TableHead className="font-heading">Listing Title</TableHead>
                  <TableHead className="font-heading">Current Price</TableHead>
                  <TableHead className="font-heading">Last Checked</TableHead>
                  <TableHead className="font-heading">Status</TableHead>
                  <TableHead className="font-heading text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {listings.map((l) => (
                  <TableRow key={l.id} data-testid={`listing-row-${l.id}`}>
                    <TableCell className="max-w-[320px]">
                      <a
                        href={l.url}
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium hover:text-primary inline-flex items-center gap-1.5 line-clamp-2"
                        data-testid={`listing-link-${l.id}`}
                      >
                        {l.title || "Etsy Listing"}
                        <ExternalLink className="w-3 h-3 shrink-0" />
                      </a>
                      {l.seller_name && (
                        <p className="text-xs text-muted-foreground mt-1">by {l.seller_name}</p>
                      )}
                    </TableCell>
                    <TableCell>
                      <span className="font-medium">{l.price || "—"}</span>
                      {l.last_price && l.last_price !== l.price && (
                        <p className="text-xs text-muted-foreground line-through">{l.last_price}</p>
                      )}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDate(l.last_checked)}
                    </TableCell>
                    <TableCell>
                      <StatusBadge status={l.status} />
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(l.id)}
                        data-testid={`delete-listing-${l.id}`}
                        className="text-foreground/70 hover:text-destructive"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </div>

        <p className="mt-6 text-xs text-muted-foreground">
          Free plan limit: 3 listings. Upgrade to Pro for unlimited monitoring.
        </p>
      </main>
    </div>
  );
}
