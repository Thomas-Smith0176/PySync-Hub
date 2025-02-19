import logging

from app.models import *
from app.repositories.playlist_repository import PlaylistRepository
from app.services.spotify_service import SpotifyService

logger = logging.getLogger(__name__)


class TrackManagerService:
    @staticmethod
    def fetch_playlist_tracks(playlist_id: int):
        """
        Syncs the tracks for a given playlist by fetching track data from Spotify
        and then updating the Track and PlaylistTrack tables.
        """
        playlist = PlaylistRepository.get_playlist(playlist_id)
        if not playlist:
            logger.error("Playlist with id %s not found", playlist_id)
            return "Playlist not found"

        if playlist.platform != 'spotify':
            logger.error("Playlist platform %s not supported for track syncing", playlist.platform)
            return "Platform not supported for track syncing"

        try:
            # Fetch the track data from Spotify using the playlist's external ID
            tracks_data = SpotifyService.get_playlist_tracks(playlist.external_id)
            logger.info("Fetched %d tracks for playlist %s", len(tracks_data), playlist.name)

            # Iterate over the fetched tracks; use the index to set the track order
            for index, track_data in enumerate(tracks_data):
                # Check if the track already exists in the Track table based on the unique constraint
                track = Track.query.filter_by(
                    platform=track_data['platform'],
                    platform_id=track_data['platform_id']
                ).first()

                # If the track is not found, create a new Track record
                if not track:
                    track = Track(
                        platform_id=track_data['platform_id'],
                        platform=track_data['platform'],
                        name=track_data['name'],
                        artist=track_data['artist'],
                        album=track_data['album'],
                        album_art_url=track_data['album_art_url'],
                        download_url=track_data.get('download_url')
                    )
                    db.session.add(track)
                    # Flush to generate the track.id without committing yet
                    db.session.flush()

                # Now add the association in the PlaylistTrack join table
                # The join table records which tracks are part of the playlist and their order.
                # The unique constraint on (playlist_id, track_id) prevents duplicate entries.
                existing_entry = PlaylistTrack.query.filter_by(
                    playlist_id=playlist.id,
                    track_id=track.id
                ).first()
                if not existing_entry:
                    playlist_track = PlaylistTrack(
                        playlist_id=playlist.id,
                        track_id=track.id,
                        track_order=index
                    )
                    db.session.add(playlist_track)

            db.session.commit()
            logger.info("Successfully synced tracks for playlist: %s", playlist.name)
            return "Tracks synced successfully"

        except Exception as e:
            logger.error("Error syncing playlist tracks for playlist %s: %s", playlist.external_id, e, exc_info=True)
            db.session.rollback()
            return "Error syncing playlist tracks"
