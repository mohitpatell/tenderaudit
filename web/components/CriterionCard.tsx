"use client";

import { useState } from "react";
import { Check, Edit2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { Criterion, ThresholdOp } from "@/lib/types";

interface CriterionCardProps {
  criterion: Criterion;
  isApproved: boolean;
  onApprove: () => void;
  onUpdate: (updated: Criterion) => void;
}

const typeStyles: Record<string, string> = {
  financial: "bg-blue-50 text-blue-700 border-blue-200",
  technical: "bg-purple-50 text-purple-700 border-purple-200",
  compliance: "bg-orange-50 text-orange-700 border-orange-200",
  documentation: "bg-slate-100 text-slate-600 border-slate-200",
};

const OPS: ThresholdOp[] = [">=", "<=", "==", "exists", "not_blacklisted"];

export function CriterionCard({ criterion, isApproved, onApprove, onUpdate }: CriterionCardProps) {
  const [editing, setEditing] = useState(false);
  const [local, setLocal] = useState<Criterion>(criterion);
  const [newDoc, setNewDoc] = useState("");

  function saveEdit() {
    onUpdate(local);
    setEditing(false);
  }

  function cancelEdit() {
    setLocal(criterion);
    setEditing(false);
  }

  function addDocument() {
    if (!newDoc.trim()) return;
    setLocal((prev) => ({ ...prev, required_documents: [...prev.required_documents, newDoc.trim()] }));
    setNewDoc("");
  }

  function removeDocument(idx: number) {
    setLocal((prev) => ({
      ...prev,
      required_documents: prev.required_documents.filter((_, i) => i !== idx),
    }));
  }

  return (
    <Card className={cn("transition-all", isApproved && "border-emerald-200 bg-emerald-50/30")}>
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-semibold text-slate-900">{criterion.name}</span>
            <Badge
              variant="outline"
              className={cn("text-xs", typeStyles[criterion.type])}
            >
              {criterion.type}
            </Badge>
            {criterion.is_mandatory && (
              <Badge variant="outline" className="text-xs text-rose-600 border-rose-200 bg-rose-50">
                mandatory
              </Badge>
            )}
            {isApproved && (
              <Badge className="text-xs bg-emerald-100 text-emerald-700 border-emerald-200" variant="outline">
                <Check className="h-3 w-3 mr-1" /> Approved
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            {!isApproved && (
              <>
                <Button size="sm" variant="outline" onClick={() => setEditing(!editing)} className="h-8 gap-1.5">
                  <Edit2 className="h-3.5 w-3.5" />
                  Edit
                </Button>
                <Button size="sm" onClick={onApprove} className="h-8 gap-1.5 bg-emerald-600 hover:bg-emerald-700">
                  <Check className="h-3.5 w-3.5" />
                  Approve
                </Button>
              </>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        <p className="text-sm text-slate-600">{criterion.description}</p>

        {/* Threshold */}
        {criterion.threshold_value !== null && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500">Threshold:</span>
            {editing ? (
              <div className="flex items-center gap-2">
                <select
                  className="text-xs border rounded px-2 py-1 bg-white"
                  value={local.threshold_operator}
                  onChange={(e) => setLocal((p) => ({ ...p, threshold_operator: e.target.value as ThresholdOp }))}
                >
                  {OPS.map((op) => <option key={op} value={op}>{op}</option>)}
                </select>
                <Input
                  type="number"
                  className="h-7 text-xs w-32"
                  value={local.threshold_value ?? ""}
                  onChange={(e) => setLocal((p) => ({ ...p, threshold_value: parseFloat(e.target.value) }))}
                />
                <Input
                  className="h-7 text-xs w-20"
                  value={local.threshold_unit ?? ""}
                  placeholder="unit"
                  onChange={(e) => setLocal((p) => ({ ...p, threshold_unit: e.target.value }))}
                />
              </div>
            ) : (
              <code className="bg-slate-100 text-slate-800 text-xs px-2 py-0.5 rounded">
                {criterion.threshold_operator} {criterion.threshold_value?.toLocaleString("en-IN")} {criterion.threshold_unit}
              </code>
            )}
          </div>
        )}

        {/* Source clause */}
        <blockquote className="border-l-2 border-primary/20 pl-3 text-xs text-slate-500 italic">
          {criterion.source_clause}
        </blockquote>

        {/* Required documents */}
        <div>
          <p className="text-xs font-medium text-slate-500 mb-2">Required Documents</p>
          <div className="flex flex-wrap gap-2">
            {(editing ? local : criterion).required_documents.map((doc, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-1 bg-slate-100 text-slate-700 text-xs px-2 py-1 rounded-full"
              >
                {doc}
                {editing && (
                  <button onClick={() => removeDocument(i)} className="ml-0.5 hover:text-rose-500">
                    <X className="h-3 w-3" />
                  </button>
                )}
              </span>
            ))}
            {editing && (
              <div className="flex items-center gap-1">
                <Input
                  className="h-6 text-xs w-40 rounded-full"
                  placeholder="Add document…"
                  value={newDoc}
                  onChange={(e) => setNewDoc(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addDocument()}
                />
                <Button size="icon" className="h-6 w-6 rounded-full" onClick={addDocument}>
                  <Plus className="h-3 w-3" />
                </Button>
              </div>
            )}
          </div>
        </div>

        {/* Edit save/cancel */}
        {editing && (
          <div className="flex gap-2 pt-1">
            <Button size="sm" onClick={saveEdit} className="h-7 text-xs">Save changes</Button>
            <Button size="sm" variant="outline" onClick={cancelEdit} className="h-7 text-xs">Cancel</Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
