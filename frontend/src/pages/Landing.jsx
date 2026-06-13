import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  ShieldCheck,
  Eye,
  AlertTriangle,
  Mail,
  Check,
  ArrowRight,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { toast } from "sonner";
import client, { setSession } from "../lib/api";
import Header from "../components/Header";

export default function Landing() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSignup = async (e) => {
    e.preventDefault();
    if (!email || !email.includes("@")) {
      toast.error("Please enter a valid email");
      return;
    }
    setLoading(true);
    try {
      await client.post("/auth/signup", { email });
      setSession(email);
      toast.success("Welcome to EtsyWatch");
      navigate("/dashboard");
    } catch (err) {
      const detail =
        err?.response?.data?.detail ||
        err?.message ||
        "Signup failed";
      const status = err?.response?.status;
      toast.error(status ? `Signup failed (${status}): ${detail}` : `Signup failed: ${detail}`);
      // eslint-disable-next-line no-console
      console.error("Signup error:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Header />

      {/* Hero */}
      <section className="max-w-6xl mx-auto px-6 lg:px-10 pt-20 pb-24 lg:grid lg:grid-cols-12 lg:gap-12">
        <div className="lg:col-span-7">
          <div className="inline-flex items-center gap-2 text-xs uppercase tracking-widest text-primary mb-6">
            <span className="brand-accent-dot" />
            <span>Etsy listing protection</span>
          </div>
          <h1 className="font-heading text-4xl sm:text-5xl lg:text-5xl font-semibold tracking-tight leading-[1.05]">
            Know the moment someone copies your Etsy listing or undercuts your price.
          </h1>
          <p className="mt-6 text-base sm:text-lg text-muted-foreground max-w-xl">
            Paste your listing URLs. We monitor them 24/7 and email you instantly with proof and a plan to fight back.
          </p>

          <form
            onSubmit={handleSignup}
            data-testid="signup-form"
            className="mt-10 flex flex-col sm:flex-row gap-3 max-w-lg"
          >
            <Input
              type="email"
              required
              placeholder="you@yourshop.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              data-testid="signup-email-input"
              className="h-12 rounded-sm border-border bg-background"
            />
            <Button
              type="submit"
              disabled={loading}
              data-testid="signup-submit-btn"
              className="h-12 px-6 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
            >
              {loading ? "Setting up..." : "Protect My Listings"}
              <ArrowRight className="ml-2 w-4 h-4" />
            </Button>
          </form>

          <p className="mt-4 text-xs text-muted-foreground">
            No password. No credit card. Free plan includes 3 listings.
          </p>
        </div>

        <div className="hidden lg:col-span-5 lg:flex items-end">
          <div className="w-full border border-border rounded-sm p-6 bg-secondary/40">
            <p className="text-xs uppercase tracking-widest text-muted-foreground mb-3">Latest alert</p>
            <div className="flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-destructive mt-0.5" />
              <div className="flex-1">
                <p className="font-heading font-semibold">Someone may have copied your listing</p>
                <p className="text-sm text-muted-foreground mt-1">"Handmade Linen Apron — Natural"</p>
                <div className="mt-3 flex items-center gap-3 text-xs">
                  <span className="px-2 py-1 rounded-sm bg-red-100 text-red-800 border border-red-200">Similarity 86%</span>
                  <span className="text-muted-foreground">Detected 2 min ago</span>
                </div>
              </div>
            </div>
            <div className="brand-rule my-5" />
            <p className="text-xs text-muted-foreground">
              Evidence screenshot saved · Cease &amp; desist message ready to send
            </p>
          </div>
        </div>
      </section>

      {/* Features strip */}
      <section className="border-y border-border bg-secondary/30">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-16 grid sm:grid-cols-3 gap-10">
          {[
            { Icon: Eye, title: "24/7 monitoring", desc: "We re-scrape your listings daily and watch for changes." },
            { Icon: ShieldCheck, title: "Copy detection", desc: "We search Etsy for similar titles and flag potential rip-offs above 70% match." },
            { Icon: Mail, title: "Instant alerts", desc: "Email with proof, similarity score, and a ready-to-send cease & desist." },
          ].map(({ Icon, title, desc }) => (
            <div key={title} data-testid={`feature-${title.replaceAll(" ", "-").toLowerCase()}`}>
              <Icon className="w-5 h-5 text-primary" />
              <h3 className="font-heading font-semibold mt-4">{title}</h3>
              <p className="text-sm text-muted-foreground mt-2">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-6 lg:px-10 py-24">
        <div className="max-w-2xl">
          <h2 className="font-heading text-3xl sm:text-4xl font-semibold tracking-tight">
            Simple pricing. Built for sellers.
          </h2>
          <p className="mt-3 text-muted-foreground">
            Start free. Upgrade when you need to watch more.
          </p>
        </div>

        <div className="mt-12 grid md:grid-cols-2 gap-6">
          <div
            data-testid="plan-free"
            className="border border-border rounded-sm p-8 bg-background"
          >
            <p className="text-xs uppercase tracking-widest text-muted-foreground">Free</p>
            <p className="mt-4 font-heading text-4xl font-semibold">$0<span className="text-base font-normal text-muted-foreground">/forever</span></p>
            <ul className="mt-6 space-y-3 text-sm">
              {["3 listings monitored", "Daily price checks", "Copy detection alerts"].map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-primary mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Button
              variant="outline"
              className="w-full mt-8 rounded-sm border-border"
              onClick={() => document.getElementById("signup-email-input")?.scrollIntoView({ behavior: "smooth" })}
              data-testid="plan-free-cta"
            >
              Start free
            </Button>
          </div>

          <div
            data-testid="plan-pro"
            className="border-2 border-primary rounded-sm p-8 bg-background relative"
          >
            <span className="absolute -top-3 left-6 text-[10px] uppercase tracking-widest bg-primary text-primary-foreground px-2 py-1 rounded-sm">
              Recommended
            </span>
            <p className="text-xs uppercase tracking-widest text-primary">Pro</p>
            <p className="mt-4 font-heading text-4xl font-semibold">$9<span className="text-base font-normal text-muted-foreground">/month</span></p>
            <ul className="mt-6 space-y-3 text-sm">
              {["Unlimited listings", "Instant alerts (no daily wait)", "Evidence screenshots saved", "Pre-written cease & desist"].map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <Check className="w-4 h-4 text-primary mt-0.5" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
            <Button
              className="w-full mt-8 rounded-sm bg-primary text-primary-foreground hover:bg-primary/90"
              onClick={() => toast.info("Pro plan coming soon. Start with Free for now.")}
              data-testid="plan-pro-cta"
            >
              Go Pro
            </Button>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="max-w-6xl mx-auto px-6 lg:px-10 py-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">© EtsyWatch. Built for independent Etsy sellers.</p>
          <p className="text-xs text-muted-foreground">Not affiliated with Etsy, Inc.</p>
        </div>
      </footer>
    </div>
  );
}
