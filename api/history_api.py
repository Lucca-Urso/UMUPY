import history


class HistoryApi:
    def history_list(self):
        return history.list_runs()

    def history_get(self, run_id):
        return history.get_run(run_id)
