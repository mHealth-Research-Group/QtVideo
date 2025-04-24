// VideoPlayer.qml
import QtQuick
import QtMultimedia // Use 5.15 or your version if needed for enums

Rectangle {
    id: root
    // anchors.fill: parent // Use if QQuickWidget resize mode needs it
    width: 400 // Or use anchors
    height: 300 // Or use anchors
    clip: true
    color: "black"

    // Properties, Signals, MediaPlayer, VideoOutput remain the same...
    property alias source: mediaPlayer.source
    property alias playbackRate: mediaPlayer.playbackRate
    property alias orientation: videoOutput.orientation
    property bool isPreview: false
    property real volume: 1.0

    property alias position: mediaPlayer.position
    property alias duration: mediaPlayer.duration
    property alias playbackState: mediaPlayer.playbackState
    property alias mediaStatus: mediaPlayer.mediaStatus
    property alias error: mediaPlayer.error
    property alias errorString: mediaPlayer.errorString

    signal qmlPositionChanged(real position)
    signal qmlDurationChanged(real duration)
    signal qmlPlaybackStateChanged(int state)
    signal qmlMediaStatusChanged(int status)
    signal qmlErrorOccurred(int error, string errorString)
    signal qmlPlaybackRateChanged(real rate)

    MediaPlayer {
        id: mediaPlayer
        audioOutput: AudioOutput { muted: root.isPreview; volume: root.volume }
        videoOutput: videoOutput
        // Forward signals...
        onPositionChanged: (position) => { root.qmlPositionChanged(position) }
        onDurationChanged: (duration) => { root.qmlDurationChanged(duration) }
        // *** Make sure state/status signals ARE connected ***
        onPlaybackStateChanged: (state) => { console.log("QML State:", state); root.qmlPlaybackStateChanged(state) }
        onMediaStatusChanged: (status) => { console.log("QML Status:", status); root.qmlMediaStatusChanged(status) }
        onErrorChanged: root.qmlErrorOccurred(mediaPlayer.error, mediaPlayer.errorString)
        onPlaybackRateChanged: (rate) => { root.qmlPlaybackRateChanged(rate) }
    }

    VideoOutput {
        id: videoOutput
        anchors.fill: parent
        fillMode: VideoOutput.PreserveAspectFit
    }

    // --- Add Status Text ---
    Text {
        id: statusText
        anchors.centerIn: parent
        width: parent.width * 0.8 // Limit width for wrapping
        wrapMode: Text.WordWrap   // Allow text wrapping
        horizontalAlignment: Text.AlignHCenter // Center text horizontally

        color: "#cccccc" // Light grey color
        font.pointSize: 14 // Adjust font size as needed

        // Dynamically set the text based on player state/status
        // Note: Comparing with integer values for states/statuses
        // 0=NoMedia, 1=Loading, 2=Loaded, 3=Prepared, 4=Buffering, 5=Stalled, 6=EndOfMedia, 7=InvalidMedia
        // 0=Stopped, 1=Playing, 2=Paused
        text: {
            var currentStatus = mediaPlayer.mediaStatus;
            var currentState = mediaPlayer.playbackState;

            if (currentStatus === 7) { // InvalidMedia
                "Error: Cannot play video";
            } else if (currentStatus === 0) { // NoMedia
                "Load a video to begin";
            } else if (currentStatus === 1 || currentStatus === 4 || currentStatus === 5) { // LoadingMedia, BufferingMedia, StalledMedia
                 // Add check for duration > 0 for buffering/stalled during playback
                 if (currentState !== 1 && currentState !== 2) { // If not already playing/paused
                    "Loading video...";
                 } else {
                     "" // Hide if buffering/stalled during playback/pause
                 }
            } else if (currentStatus === 6) { // EndOfMedia
                "Video ended";
            } else if (currentState === 0) { // StoppedState (and media is loaded/prepared)
                "Press Play to begin";
            } else {
                // Covers PlayingState (1) and PausedState (2)
                ""; // Hide text when playing or paused
            }
        }

        // Text is visible only if the text content is not empty
        visible: text !== ""
    }
    // --- End Status Text ---


    // Methods callable FROM Python (Remain the same)
    function play() { mediaPlayer.play(); }
    function pause() { mediaPlayer.pause(); }
    function stop() { mediaPlayer.stop(); }
    function seek(newPosition) {
        // Add check for seekable status
        if (mediaPlayer.seekable) {
            mediaPlayer.setPosition(newPosition);
        } else {
             console.warn("QML: Attempted seek on non-seekable media.")
        }
    }
}