#!/usr/bin/env python3
"""GitHub Copilot PR-review helper. Needs an authenticated `gh`.

Usage:
  copilot_review.py OWNER/REPO PR status
      Latest Copilot review: submittedAt, the commit it reviewed, and whether
      that commit is the PR's current head.
  copilot_review.py OWNER/REPO PR list
      Every unresolved review thread, following pagination past 100.
  copilot_review.py OWNER/REPO PR resolve THREAD_ID "reply text"
      Reply to the thread, then resolve it; exits non-zero unless the thread
      reads back as resolved.
  copilot_review.py OWNER/REPO PR rerequest
      Request a Copilot review of the current head.
"""
import json
import subprocess
import sys

BOT = "copilot-pull-request-reviewer"


def gh_graphql(query, **variables):
    args = ["gh", "api", "graphql", "-f", f"query={query}"]
    for k, v in variables.items():
        flag = "-F" if isinstance(v, int) else "-f"
        args += [flag, f"{k}={v}"]
    out = subprocess.run(args, check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    if data.get("errors"):
        sys.exit(f"graphql error: {data['errors']}")
    return data["data"]


def status(owner, name, pr):
    d = gh_graphql("""
      query($owner:String!,$name:String!,$pr:Int!){
        repository(owner:$owner,name:$name){pullRequest(number:$pr){
          headRefOid
          reviews(last:50){nodes{author{login} submittedAt state commit{oid}}}
        }}}""", owner=owner, name=name, pr=pr)["repository"]["pullRequest"]
    reviews = [r for r in d["reviews"]["nodes"]
               if r["author"] and r["author"]["login"].startswith(BOT)]
    head = d["headRefOid"]
    if not reviews:
        print(f"head={head[:12]} copilot_reviews=0")
        return
    last = reviews[-1]
    oid = (last["commit"] or {}).get("oid", "")
    print(f"head={head[:12]} last_review_at={last['submittedAt']} "
          f"last_review_commit={oid[:12]} reviewed_head={'yes' if oid == head else 'no'}")


def unresolved(owner, name, pr):
    threads, after = [], None
    while True:
        d = gh_graphql("""
          query($owner:String!,$name:String!,$pr:Int!,$after:String){
            repository(owner:$owner,name:$name){pullRequest(number:$pr){
              reviewThreads(first:100,after:$after){
                pageInfo{hasNextPage endCursor}
                nodes{id isResolved isOutdated path line
                      comments(first:1){nodes{author{login} body}}}
              }}}}""", owner=owner, name=name, pr=pr,
            **({"after": after} if after else {}))
        page = d["repository"]["pullRequest"]["reviewThreads"]
        threads += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            break
        after = page["pageInfo"]["endCursor"]
    return [t for t in threads if not t["isResolved"]], len(threads)


def list_threads(owner, name, pr):
    open_threads, total = unresolved(owner, name, pr)
    for t in open_threads:
        c = t["comments"]["nodes"][0] if t["comments"]["nodes"] else {}
        who = (c.get("author") or {}).get("login", "?")
        body = (c.get("body") or "").replace("\n", " ")[:160]
        flag = " outdated" if t["isOutdated"] else ""
        print(f"{t['id']} {t['path']}:{t['line']}{flag} [{who}] {body}")
    print(f"THREADS: {total} UNRESOLVED: {len(open_threads)}")


def resolve(thread_id, reply):
    gh_graphql("""
      mutation($id:ID!,$body:String!){
        addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$id,body:$body}){comment{id}}
      }""", id=thread_id, body=reply)
    d = gh_graphql("""
      mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}
      """, id=thread_id)
    if not d["resolveReviewThread"]["thread"]["isResolved"]:
        sys.exit(f"{thread_id}: resolve did not take effect")
    print(f"{thread_id}: replied and resolved")


def rerequest(repo, pr):
    subprocess.run(["gh", "api", "-X", "POST",
                    f"repos/{repo}/pulls/{pr}/requested_reviewers",
                    "-f", f"reviewers[]={BOT}[bot]"],
                   check=True, capture_output=True)
    print("copilot review requested")


def main(argv):
    if len(argv) < 4:
        sys.exit(__doc__)
    repo, pr, cmd = argv[1], int(argv[2]), argv[3]
    owner, name = repo.split("/", 1)
    if cmd == "status":
        status(owner, name, pr)
    elif cmd == "list":
        list_threads(owner, name, pr)
    elif cmd == "resolve" and len(argv) == 6:
        resolve(argv[4], argv[5])
    elif cmd == "rerequest":
        rerequest(repo, pr)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
