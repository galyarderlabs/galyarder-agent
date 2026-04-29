import { useEffect, useState } from "react";
import { useClient } from "@/providers/ClientProvider";
import { 
  listApprovals, handleApproval, 
  listLearning, handleLearning,
  listProfiles 
} from "@/lib/api";
import type { ApprovalRecord, LearningCandidate, CharacterProfile } from "@/lib/types";
import { Button } from "./ui/button";
import { ScrollArea } from "./ui/scroll-area";

export function ControlRoom() {
  const { token } = useClient();
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [learning, setLearning] = useState<LearningCandidate[]>([]);
  const [profiles, setProfiles] = useState<CharacterProfile[]>([]);

  const refresh = async () => {
    try {
      const [appr, learn, prof] = await Promise.all([
        listApprovals(token),
        listLearning(token),
        listProfiles(token)
      ]);
      setApprovals(appr.filter(a => a.status === "pending"));
      setLearning(learn.filter(l => l.status === "pending"));
      setProfiles(prof);
    } catch (e) {
      console.error("ControlRoom refresh failed", e);
    }
  };

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 30000);
    return () => clearInterval(interval);
  }, [token]);

  return (
    <div className="flex h-full flex-col bg-background border-l">
      <div className="p-4 border-b font-semibold flex items-center justify-between">
        Control Room
        <Button variant="ghost" size="sm" onClick={refresh}>Refresh</Button>
      </div>
      <ScrollArea className="flex-1 p-4">
        <div className="space-y-6">
          <section>
            <h3 className="text-sm font-medium mb-3 text-muted-foreground uppercase tracking-wider">Approvals</h3>
            {approvals.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No pending approvals.</p>
            ) : (
              approvals.map(a => (
                <div key={a.id} className="p-3 border rounded-md mb-2 bg-card text-card-foreground">
                  <div className="font-bold text-sm">{a.tool_name}</div>
                  <pre className="text-[10px] bg-muted p-1 mt-1 overflow-x-auto">
                    {JSON.stringify(a.tool_args, null, 2)}
                  </pre>
                  <div className="flex gap-2 mt-2">
                    <Button size="sm" onClick={() => handleApproval(token, a.id, "approve").then(refresh)}>Approve</Button>
                    <Button size="sm" variant="destructive" onClick={() => handleApproval(token, a.id, "deny").then(refresh)}>Deny</Button>
                  </div>
                </div>
              ))
            )}
          </section>

          <section>
            <h3 className="text-sm font-medium mb-3 text-muted-foreground uppercase tracking-wider">Learning</h3>
            {learning.length === 0 ? (
              <p className="text-sm text-muted-foreground italic">No candidates.</p>
            ) : (
              learning.map(l => (
                <div key={l.id} className="p-3 border rounded-md mb-2 bg-card text-card-foreground">
                  <div className="font-bold text-sm">[{l.kind}] {l.title}</div>
                  <p className="text-xs text-muted-foreground mt-1">{l.rationale}</p>
                  <div className="flex gap-2 mt-2">
                    <Button size="sm" onClick={() => handleLearning(token, l.id, "apply").then(refresh)}>Apply</Button>
                    <Button size="sm" variant="destructive" onClick={() => handleLearning(token, l.id, "reject").then(refresh)}>Reject</Button>
                  </div>
                </div>
              ))
            )}
          </section>

          <section>
            <h3 className="text-sm font-medium mb-3 text-muted-foreground uppercase tracking-wider">Profiles</h3>
            <div className="grid grid-cols-2 gap-2">
              {profiles.map(p => (
                <div key={p.id} className="p-2 border rounded-md text-center text-xs hover:bg-accent cursor-pointer">
                  {p.name}
                </div>
              ))}
            </div>
          </section>
        </div>
      </ScrollArea>
    </div>
  );
}
