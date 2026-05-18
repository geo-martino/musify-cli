from mytunes_cli.operations._base import LocalLibraryOperation


class Save(LocalLibraryOperation):
    async def run(self) -> None:
        results = await self.library.save_playlists(dry_run=self.state.dry_run)
        self.library.log_save_playlists_results(results)
