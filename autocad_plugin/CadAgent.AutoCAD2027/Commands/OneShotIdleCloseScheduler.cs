namespace CadAgent.AutoCAD2027.Commands;

public sealed class OneShotIdleCloseScheduler
{
    private readonly Action<EventHandler> _subscribe;
    private readonly Action<EventHandler> _unsubscribe;
    private readonly Action _close;
    private int _fired;
    private int _scheduled;

    public OneShotIdleCloseScheduler(
        Action<EventHandler> subscribe,
        Action<EventHandler> unsubscribe,
        Action close)
    {
        _subscribe = subscribe ?? throw new ArgumentNullException(nameof(subscribe));
        _unsubscribe = unsubscribe ?? throw new ArgumentNullException(nameof(unsubscribe));
        _close = close ?? throw new ArgumentNullException(nameof(close));
    }

    public void Schedule()
    {
        if (Interlocked.Exchange(ref _scheduled, 1) != 0)
        {
            return;
        }

        EventHandler handler = null!;
        handler = (_, _) =>
        {
            if (Interlocked.Exchange(ref _fired, 1) != 0)
            {
                return;
            }

            _unsubscribe(handler);
            _close();
        };

        _subscribe(handler);
    }
}
