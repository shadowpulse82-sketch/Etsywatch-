import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Save } from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Switch } from "../components/ui/switch";
import { toast } from "sonner";
import client, { getSession } from "../lib/api";
import Header from "../components/Header";

export default function AlertSettings() {
  const navigate = useNavigate();
  const [settings, setSettings] = useState({
    email: "",
    shop_name: "",
    alert_on_price_undercut: true,
    alert_on_similar_listing: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!getSession()) {
      navigate("/");
      return;
    }
    (async () => {
      try {
        const res = await client.get("/settings");
        setSettings(res.data);
      } catch (err) {
        toast.error(err?.response?.data?.detail || "Failed to load settings");
      } finally {
        setLoading(false);
      }
    })();
  }, [navigate]);

  const save = async () => {
    setSaving(true);
    try {
      const res = await client.put("/settings", {
        shop_name: settings.shop_name,
        alert_on_price_undercut: settings.alert_on_price_undercut,
        alert_on_similar_listing: settings.alert_on_similar_listing,
      });
      setSettings(res.data);
      toast.success("Settings saved");
    } catch (err) {
      toast.error(err?.response?.data?.detail || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background">
        <Header />
        <div className="p-10 text-center text-sm text-muted-foreground">
          <Loader2 className="w-5 h-5 animate-spin inline mr-2" />
          Loading...
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />
      <main className="max-w-3xl mx-auto px-6 lg:px-10 py-12" data-testid="settings-page">
        <p className="text-xs uppercase tracking-widest text-primary flex items-center gap-2">
          <span className="brand-accent-dot" /> Alert Settings
        </p>
        <h1 className="mt-3 font-heading text-3xl sm:text-4xl font-semibold tracking-tight">
          Tune your alerts
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Decide when EtsyWatch should email you.
        </p>

        <div className="mt-10 space-y-8">
          <div>
            <Label htmlFor="email" className="text-sm font-medium">
              Alert email
            </Label>
            <Input
              id="email"
              value={settings.email}
              disabled
              data-testid="settings-email-input"
              className="mt-2 h-11 rounded-sm border-border bg-secondary/50"
            />
            <p className="mt-2 text-xs text-muted-foreground">
              This is the email you signed up with.
            </p>
          </div>

          <div>
            <Label htmlFor="shop_name" className="text-sm font-medium">
              Your Etsy shop name (used in cease &amp; desist message)
            </Label>
            <Input
              id="shop_name"
              placeholder="e.g. LinenAndOakStudio"
              value={settings.shop_name || ""}
              onChange={(e) =>
                setSettings({ ...settings, shop_name: e.target.value })
              }
              data-testid="settings-shop-input"
              className="mt-2 h-11 rounded-sm border-border bg-background"
            />
          </div>

          <div className="brand-rule" />

          <div className="flex items-start justify-between gap-6">
            <div>
              <Label htmlFor="undercut" className="text-sm font-medium">
                Alert me when my price is undercut
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                We compare current price to the last saved value.
              </p>
            </div>
            <Switch
              id="undercut"
              checked={settings.alert_on_price_undercut}
              onCheckedChange={(v) =>
                setSettings({ ...settings, alert_on_price_undercut: v })
              }
              data-testid="toggle-price-undercut"
            />
          </div>

          <div className="flex items-start justify-between gap-6">
            <div>
              <Label htmlFor="similar" className="text-sm font-medium">
                Alert me when a similar listing is detected
              </Label>
              <p className="text-xs text-muted-foreground mt-1">
                Triggered when another shop's listing exceeds 70% title similarity.
              </p>
            </div>
            <Switch
              id="similar"
              checked={settings.alert_on_similar_listing}
              onCheckedChange={(v) =>
                setSettings({ ...settings, alert_on_similar_listing: v })
              }
              data-testid="toggle-similar-listing"
            />
          </div>

          <div className="pt-4">
            <Button
              onClick={save}
              disabled={saving}
              data-testid="save-settings-btn"
              className="rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              Save changes
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
