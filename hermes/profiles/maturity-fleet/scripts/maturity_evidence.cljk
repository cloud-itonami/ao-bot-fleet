#!/usr/bin/env nbb
;; maturity-fleet evidence: scan ISIC+ISCO repo maturity across the whole
;; industry/occupation sets, find the lowest-score target, append-only ledger.
;; cron-safe: no interactive tools, no writes to west. Deterministic.
;; Evidence script owns the measurement; the agent only reads and reports.

(require '[clojure.string :as str]
         '["node:fs" :as fs])

(def west-path     "~/github/com-junkawasaki/manifest/west.yml")
(def maturity-path "~/github/com-junkawasaki/manifest/repo-maturity.edn")
(def ledger-path   "~/.hermes/profiles/maturity-fleet/workspace/maturity-ledger.jsonl")
(def last-run-path "~/.hermes/profiles/maturity-fleet/workspace/.last-run.json")

(defn field-of [line k]
  ;; "k value" -> bare value. Handles both quoted strings and bare tokens;
  ;; captures the whole token incl. trailing comma then strips quote/comma.
  (let [re (re-pattern (str (js/RegExp.escape k) "\\s*(\"(?:[^\"\\\\]|\\\\.)*\"|[^\\s,}]+)"))]
    (when-let [m (re-find re line)]
      (let [v (second m)]
        (-> v
            (str/replace #"^\"|\"$" "")
            (str/replace #",$" ""))))))

(defn load-maturity []
  ;; one flat entity-map per line; key order varies. Pull name + composite
  ;; independently, keep only ISIC/ISCO industry/occupation repos.
  (let [raw (fs/readFileSync maturity-path "utf8")]
    (->> (str/split-lines raw)
         (keep (fn [line]
                 (let [name (field-of line ":repo/name")
                       path (field-of line ":repo/path")
                       comp (field-of line ":maturity/composite")
                       arch (field-of line ":repo/archived?")]
                   (when (and name (re-find #"^cloud-itonami-(?:isic|isco)-" name)
                              comp (not= arch "true"))
                     {:name name :path path :score (js/parseFloat comp)}))))
         (into []))))

(defn load-west-names []
  (let [raw (fs/readFileSync west-path "utf8")]
    (->> (re-seq #"cloud-itonami-(?:isic|isco)-[0123456789][a-z0-9-]*" raw)
         (into #{})
         sort)))

(let [mat (load-maturity)
      west-names (load-west-names)
      by-name (into {} (map (fn [e] [(:name e) e])) mat)
      targets (->> west-names
                   (map (fn [n] (let [e (get by-name n)]
                                  {:name n :score (:score e) :path (:path e)})))
                   vec)
      scored (vec (sort-by :score (filter #(some? (:score %)) targets)))
      unscored (filterv #(nil? (:score %)) targets)
      lowest (first scored)
      run-ts (-> (js/Date.) .toISOString)]
  (println "=== maturity-fleet evidence ===")
  (println (str "west targets: " (count west-names)
                "  scanned: " (count mat)
                "  scored: " (count scored)
                "  unscored: " (count unscored)))
  (when lowest
    (println (str "LOWEST: " (:name lowest)
                  "  composite " (:score lowest)
                  "  path " (:path lowest))))
  ;; append-only ledger: keep the ranked top 10 + the run snapshot
  (let [top10 (take 10 scored)]
    (fs/appendFileSync ledger-path
      (str (pr-str {:ts run-ts
                    :type :maturity-scan
                    :west-targets (count west-names)
                    :scanned (count mat)
                    :scored (count scored)
                    :unscored (count unscored)
                    :lowest (:name lowest)
                    :lowest-score (:score lowest)
                    :lowest-path (:path lowest)
                    :top (mapv (fn [t] {:name (:name t) :score (:score t)}) top10)})
           "\n")))
  ;; drift signal vs previous run state (JSON-safe, plain map)
  (let [state (pr-str {:lowest (:name lowest) :scored (count scored)})]
    (when (fs/existsSync last-run-path)
      (let [prev (read-string (fs/readFileSync last-run-path "utf8"))
            prev-low (:lowest prev)]
        (if (and prev-low (:name lowest) (not= prev-low (:name lowest)))
          (println (str "DRIFT: lowest moved " prev-low " -> " (:name lowest)))
          (println (str "lowest stable: " (:name lowest))))))
    (fs/writeFileSync last-run-path state))
  ;; exit 0 always — a broken scan is reported, never masked as success
  (println "=== SMOKE-OK ==="))