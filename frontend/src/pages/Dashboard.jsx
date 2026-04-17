import { useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  Activity,
  ArrowLeft,
  Clock,
  FileText,
  Globe,
  ChevronDown,
  BarChart3,
  Pill,
  Brain,
  Database,
  User,
} from "lucide-react";
import Timeline from "../components/Timeline";
import TrendChart from "../components/TrendChart";
import DrugInteractions from "../components/DrugInteractions";
import AISummary from "../components/AISummary";
import EntityExplorer from "../components/EntityExplorer";

const TABS = [
  { id: "timeline", icon: Clock },
  { id: "trends", icon: BarChart3 },
  { id: "drugs", icon: Pill },
  { id: "summary", icon: Brain },
  { id: "entities", icon: Database },
];

const LANGUAGES = [
  { code: "en", label: "English" },
  { code: "hi", label: "हिंदी" },
  { code: "mr", label: "मराठी" },
];

export default function Dashboard({ data, onBack, onChangeLanguage }) {
  const { t, i18n } = useTranslation();
  const [activeTab, setActiveTab] = useState("timeline");
  const [showLangMenu, setShowLangMenu] = useState(false);

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-neutral-500 text-lg mb-4">
            No analysis data available
          </p>
          <button
            onClick={onBack}
            className="px-6 py-2 bg-[#292A2C] text-white rounded-md hover:bg-[#363738] border border-white/8"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  const {
    patient,
    timeline,
    lab_series,
    trends,
    drug_interactions,
    summary,
    entities,
  } = data;

  return (
    <div className="min-h-screen">
      {/* Top Navigation */}
      <nav className="nav-glass sticky top-0 z-50 px-6 py-3">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="flex items-center gap-1.5 text-sm text-neutral-400 hover:text-white transition-colors"
              id="back-button"
            >
              <ArrowLeft className="w-4 h-4" />
              {t("dashboard.back_home")}
            </button>
            <div className="h-6 w-px bg-white/10" />
            <div className="flex items-center gap-2">
              <img
                src="/logo.png"
                alt="MedAnalyzer"
                className="w-8 h-8 rounded-md object-cover"
              />
              <span className="font-bold text-white">{t("app_name")}</span>
            </div>
          </div>

          {/* Language selector */}
          <div className="relative">
            <button
              onClick={() => setShowLangMenu(!showLangMenu)}
              className="flex items-center gap-2 px-3 py-2 rounded-md bg-white/5 hover:bg-white/10 border border-white/8 transition-all text-sm"
            >
              <Globe className="w-4 h-4 text-neutral-400" />
              <span className="text-neutral-200">
                {LANGUAGES.find((l) => l.code === i18n.language)?.label}
              </span>
              <ChevronDown className="w-3 h-3 text-neutral-500" />
            </button>
            {showLangMenu && (
              <motion.div
                initial={{ opacity: 0, y: -5 }}
                animate={{ opacity: 1, y: 0 }}
                className="absolute right-0 mt-1 w-40 rounded-md shadow-2xl overflow-hidden z-50 bg-[#1a1a1c] border border-white/8"
              >
                {LANGUAGES.map((lang) => (
                  <button
                    key={lang.code}
                    onClick={() => {
                      onChangeLanguage(lang.code);
                      setShowLangMenu(false);
                    }}
                    className={`w-full px-4 py-2.5 text-left text-sm flex items-center gap-2 hover:bg-white/5 transition-colors ${
                      i18n.language === lang.code
                        ? "bg-white/5 font-semibold text-white"
                        : "text-neutral-400"
                    }`}
                  >
                    <Globe className="w-3.5 h-3.5 text-neutral-500" />
                    <span>{lang.label}</span>
                  </button>
                ))}
              </motion.div>
            )}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-6 py-6">
        {/* Patient Header */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-6 mb-6"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 bg-[#292A2C] rounded-md flex items-center justify-center text-2xl font-bold text-white border border-white/8">
                {patient?.name?.[0]?.toUpperCase() || (
                  <User className="w-6 h-6" />
                )}
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white">
                  {patient?.name || "Patient"}
                </h1>
                <div className="flex items-center gap-3 text-sm text-neutral-500 mt-0.5">
                  <span>ID: {patient?.external_id}</span>
                  {patient?.gender && <span>· {patient.gender}</span>}
                  {patient?.date_of_birth && (
                    <span>· DOB: {patient.date_of_birth}</span>
                  )}
                  {data.mode === "demo" && (
                    <span className="px-3 py-1 bg-white/10 text-white rounded-lg text-xs font-bold border border-white/10 h-fit flex items-center">
                      DEMO
                    </span>
                  )}
                </div>
              </div>
            </div>
            <div className="flex items-stretch gap-3">
              <div className="text-center px-5 py-3 bg-white/[0.04] rounded-md border border-white/[0.06] flex flex-col justify-center">
                <p className="text-lg font-bold text-white leading-tight">
                  {data.reports?.length || patient?.report_count || "—"}
                </p>
                <p className="text-xs text-neutral-500 mt-0.5">
                  {t("dashboard.report_count")}
                </p>
              </div>
              <div className="text-center px-5 py-3 bg-white/[0.04] rounded-md border border-white/[0.06] flex flex-col justify-center">
                <p className="text-sm font-bold text-white leading-tight">
                  {patient?.updated_at
                    ? new Date(patient.updated_at).toLocaleDateString()
                    : "—"}
                </p>
                <p className="text-xs text-neutral-500 mt-0.5">
                  {t("dashboard.last_updated")}
                </p>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Tab Navigation — all same style */}
        <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center gap-2 px-5 py-3 rounded-md font-medium text-sm whitespace-nowrap transition-all duration-200 ${
                  isActive
                    ? "bg-[#292A2C] text-white border border-white/10"
                    : "bg-white/[0.03] text-neutral-500 hover:bg-white/[0.06] hover:text-neutral-300 border border-white/[0.04]"
                }`}
                id={`tab-${tab.id}`}
              >
                <Icon className="w-4 h-4" />
                {t(`dashboard.tabs.${tab.id}`)}
              </button>
            );
          })}
        </div>

        {/* Tab Content */}
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === "timeline" && <Timeline events={timeline || []} />}
          {activeTab === "trends" && (
            <TrendChart trends={trends || []} labSeries={lab_series || {}} />
          )}
          {activeTab === "drugs" && (
            <DrugInteractions data={drug_interactions || {}} />
          )}
          {activeTab === "summary" && (
            <AISummary summary={summary || {}} patient={patient} />
          )}
          {activeTab === "entities" && (
            <EntityExplorer
              entities={entities || data.reports?.[0]?.entities || {}}
            />
          )}
        </motion.div>
      </main>
    </div>
  );
}
