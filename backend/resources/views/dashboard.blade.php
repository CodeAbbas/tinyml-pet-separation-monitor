<!DOCTYPE html>
<html lang="en" class="h-full bg-slate-950 text-slate-100 antialiased selection:bg-teal-500 selection:text-white">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
  <meta http-equiv="refresh" content="5">
  <meta name="theme-color" content="#020617">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <title>Pet Welfare Monitor</title>

  <!-- Tailwind CSS v4 Browser Build -->
  <script src="https://unpkg.com/@tailwindcss/browser@4"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">

  <style>
    body {
      font-family: 'Plus Jakarta Sans', system-ui, -apple-system, sans-serif;
      padding-bottom: env(safe-area-inset-bottom, 80px);
    }
  </style>
</head>
<body class="min-h-full bg-slate-950 text-slate-100 flex flex-col justify-between">

  <!-- Mobile/PWA Shell Container -->
  <div class="w-full max-w-2xl mx-auto px-4 pt-4 pb-24 sm:px-6 sm:pt-8 space-y-6">

    <!-- App Header Bar -->
    <header class="flex items-center justify-between bg-slate-900/80 backdrop-blur-xl border border-slate-800/80 rounded-2xl p-4 shadow-xl">
      <div class="flex items-center gap-3">
        <div class="relative flex h-10 w-10 items-center justify-center rounded-xl bg-teal-500/10 border border-teal-500/20 text-teal-400 font-bold">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
          </svg>
          <span class="absolute -top-0.5 -right-0.5 flex h-2.5 w-2.5">
            <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-teal-400 opacity-75"></span>
            <span class="relative inline-flex rounded-full h-2.5 w-2.5 bg-teal-500"></span>
          </span>
        </div>
        <div>
          <h1 class="text-base font-bold tracking-tight text-white leading-tight">Pet Welfare Monitor</h1>
          <p class="text-xs font-medium text-slate-400">Edge-detected Screening</p>
        </div>
      </div>

      <div class="flex items-center gap-2 bg-slate-950/60 border border-slate-800 px-3 py-1.5 rounded-full text-xs font-semibold text-slate-300">
        <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
        <span>gateway.py active</span>
      </div>
    </header>

    <!-- Status Hero Banner -->
    @php
      $isAlert = $latest && $latest->composite_z >= 3;
      $isModerate = $latest && $latest->composite_z >= 1.5 && $latest->composite_z < 3;
    @endphp
    
    <div class="relative overflow-hidden rounded-3xl border transition-all duration-300 p-6 
      {{ $isAlert ? 'bg-gradient-to-br from-red-950/60 via-slate-900 to-slate-950 border-red-500/30 shadow-2xl shadow-red-950/40' : 
        ($isModerate ? 'bg-gradient-to-br from-amber-950/60 via-slate-900 to-slate-950 border-amber-500/30 shadow-2xl shadow-amber-950/40' : 
                       'bg-gradient-to-br from-teal-950/60 via-slate-900 to-slate-950 border-teal-500/30 shadow-2xl shadow-teal-950/20') }}">
      
      <div class="flex justify-between items-start">
        <div>
          <span class="text-xs font-bold uppercase tracking-wider text-slate-400">Current Health Index</span>
          <div class="flex items-baseline gap-2 mt-1">
            <span class="text-4xl font-extrabold tracking-tight font-mono {{ $isAlert ? 'text-red-400' : ($isModerate ? 'text-amber-400' : 'text-teal-400') }}">
              {{ $latest ? number_format($latest->composite_z, 2) : '—' }}
            </span>
            <span class="text-sm font-semibold text-slate-400">Composite Z</span>
          </div>
        </div>

        <span class="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider border
          {{ $isAlert ? 'bg-red-500/10 text-red-400 border-red-500/20' : 
            ($isModerate ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : 
                           'bg-teal-500/10 text-teal-400 border-teal-500/20') }}">
          {{ $isAlert ? 'Alert Triggered' : ($isModerate ? 'Elevated' : 'Normal') }}
        </span>
      </div>

      <!-- Meter Gauge Visual -->
      <div class="mt-6">
        <div class="flex justify-between text-[11px] font-semibold text-slate-400 mb-1.5">
          <span>Baseline (0.0)</span>
          <span>Moderate (1.5)</span>
          <span>Severe (3.0+)</span>
        </div>
        <div class="h-2 w-full bg-slate-800 rounded-full overflow-hidden p-0.5 border border-slate-700/50">
          @php
            $zVal = $latest ? min(max($latest->composite_z, 0), 4) : 0;
            $percentage = ($zVal / 4) * 100;
          @endphp
          <div class="h-full rounded-full transition-all duration-500 {{ $isAlert ? 'bg-red-500' : ($isModerate ? 'bg-amber-500' : 'bg-teal-400') }}" style="width: {{ $percentage }}%"></div>
        </div>
      </div>
    </div>

    <!-- Quick Stats Grid -->
    <div class="grid grid-cols-2 gap-3 sm:gap-4">
      <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between">
        <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Total Episodes</span>
        <div class="mt-2 flex items-baseline justify-between">
          <span class="text-2xl font-bold font-mono text-white">{{ $total }}</span>
          <span class="text-xs text-slate-500 font-medium">Recorded</span>
        </div>
      </div>

      <div class="bg-slate-900/60 border border-slate-800/80 rounded-2xl p-4 flex flex-col justify-between">
        <span class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Last Detection</span>
        <div class="mt-2 flex items-baseline justify-between">
          <span class="text-base font-bold text-white truncate">
            {{ $latest ? $latest->occurred_at->diffForHumans() : 'None yet' }}
          </span>
        </div>
      </div>
    </div>

    <!-- Episodes List / Logs -->
    <section class="space-y-3">
      <div class="flex items-center justify-between px-1">
        <h2 class="text-sm font-bold uppercase tracking-wider text-slate-300">Recent Behavioural Logs</h2>
        <span class="text-xs text-slate-500 font-medium">Auto-refreshing 5s</span>
      </div>

      @if($episodes->isEmpty())
        <div class="bg-slate-900/40 border border-dashed border-slate-800 rounded-2xl p-8 text-center space-y-2">
          <div class="mx-auto w-10 h-10 rounded-full bg-slate-800/60 flex items-center justify-center text-slate-500">
            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p class="text-sm font-semibold text-slate-300">No episodes logged yet</p>
          <p class="text-xs text-slate-500 max-w-xs mx-auto">Start <code class="bg-slate-800 text-teal-400 px-1.5 py-0.5 rounded font-mono">gateway.py</code> and trigger restless behaviour to record telemetry.</p>
        </div>
      @else
        <!-- Mobile Card Feed (Visible on small screens) -->
        <div class="space-y-3 sm:hidden">
          @foreach($episodes as $e)
            @php
              $sev = strtolower($e->severity);
              $badgeClass = match($sev) {
                'high' => 'bg-red-500/10 text-red-400 border-red-500/20',
                'moderate' => 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                default => 'bg-teal-500/10 text-teal-400 border-teal-500/20',
              };
            @endphp
            <div class="bg-slate-900/80 border border-slate-800 rounded-2xl p-4 space-y-3">
              <div class="flex items-center justify-between border-b border-slate-800/60 pb-2.5">
                <div class="flex items-center gap-2">
                  <span class="text-xs font-mono font-bold text-slate-400">{{ $e->occurred_at->format('d M H:i:s') }}</span>
                  <span class="text-[10px] bg-slate-800 text-slate-300 px-2 py-0.5 rounded-md font-mono">{{ $e->device_id }}</span>
                </div>
                <span class="px-2.5 py-0.5 rounded-full text-[10px] font-extrabold uppercase border {{ $badgeClass }}">
                  {{ strtoupper($e->severity) }}
                </span>
              </div>

              <div class="grid grid-cols-2 gap-2 text-xs">
                <div class="bg-slate-950/50 p-2 rounded-xl border border-slate-800/40">
                  <span class="text-[10px] text-slate-500 uppercase block font-semibold">Composite Z</span>
                  <span class="font-mono font-bold text-slate-200 text-sm">{{ number_format($e->composite_z, 2) }}</span>
                </div>
                <div class="bg-slate-950/50 p-2 rounded-xl border border-slate-800/40">
                  <span class="text-[10px] text-slate-500 uppercase block font-semibold">Transition Rate</span>
                  <span class="font-mono text-slate-300">{{ number_format($e->f_transition_rate, 1) }}/min</span>
                </div>
                <div class="bg-slate-950/50 p-2 rounded-xl border border-slate-800/40">
                  <span class="text-[10px] text-slate-500 uppercase block font-semibold">Dwell Entropy</span>
                  <span class="font-mono text-slate-300">{{ number_format($e->f_dwell_entropy, 2) }}</span>
                </div>
                <div class="bg-slate-950/50 p-2 rounded-xl border border-slate-800/40">
                  <span class="text-[10px] text-slate-500 uppercase block font-semibold">Activity</span>
                  <span class="font-mono text-slate-300">{{ number_format($e->f_activity, 1) }} px/s</span>
                </div>
              </div>
            </div>
          @endforeach
        </div>

        <!-- Desktop Responsive Table (Visible on larger screens) -->
        <div class="hidden sm:block overflow-hidden bg-slate-900/60 border border-slate-800 rounded-2xl shadow-xl">
          <div class="overflow-x-auto">
            <table class="w-full text-left text-xs">
              <thead>
                <tr class="border-b border-slate-800 bg-slate-900/90 text-slate-400 uppercase tracking-wider text-[10px] font-bold">
                  <th class="py-3 px-4">Time</th>
                  <th class="py-3 px-4">Device</th>
                  <th class="py-3 px-4">Comp. Z</th>
                  <th class="py-3 px-4">Severity</th>
                  <th class="py-3 px-4">Transitions</th>
                  <th class="py-3 px-4">Entropy</th>
                  <th class="py-3 px-4">Pos Var</th>
                  <th class="py-3 px-4">Activity</th>
                </tr>
              </thead>
              <tbody class="divide-y divide-slate-800/60 font-mono text-slate-300">
                @foreach($episodes as $e)
                  @php
                    $sev = strtolower($e->severity);
                    $badgeClass = match($sev) {
                      'high' => 'bg-red-500/10 text-red-400 border-red-500/20',
                      'moderate' => 'bg-amber-500/10 text-amber-400 border-amber-500/20',
                      default => 'bg-teal-500/10 text-teal-400 border-teal-500/20',
                    };
                  @endphp
                  <tr class="hover:bg-slate-800/30 transition-colors">
                    <td class="py-3 px-4 font-sans font-medium text-slate-300 whitespace-nowrap">{{ $e->occurred_at->format('d M H:i:s') }}</td>
                    <td class="py-3 px-4 text-slate-400">{{ $e->device_id }}</td>
                    <td class="py-3 px-4 font-bold text-white">{{ number_format($e->composite_z, 2) }}</td>
                    <td class="py-3 px-4 font-sans">
                      <span class="px-2 py-0.5 rounded-full text-[10px] font-bold border {{ $badgeClass }}">
                        {{ strtoupper($e->severity) }}
                      </span>
                    </td>
                    <td class="py-3 px-4">{{ number_format($e->f_transition_rate, 1) }}/m</td>
                    <td class="py-3 px-4">{{ number_format($e->f_dwell_entropy, 2) }}</td>
                    <td class="py-3 px-4">{{ number_format($e->f_position_var, 1) }}</td>
                    <td class="py-3 px-4">{{ number_format($e->f_activity, 1) }} px/s</td>
                  </tr>
                @endforeach
              </tbody>
            </table>
          </div>
        </div>
      @endif
    </section>

  </div>

  <!-- Mobile Bottom Tab Navigation (PWA Touch Target) -->
  <nav class="fixed bottom-0 left-0 right-0 z-50 bg-slate-900/90 backdrop-blur-xl border-t border-slate-800 px-6 py-2.5 max-w-2xl mx-auto sm:rounded-t-2xl">
    <div class="flex items-center justify-around">
      <button class="flex flex-col items-center gap-1 text-teal-400 focus:outline-none">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
        </svg>
        <span class="text-[10px] font-bold tracking-tight">Logs</span>
      </button>

      <button class="flex flex-col items-center gap-1 text-slate-500 hover:text-slate-300 transition-colors focus:outline-none">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 18h.01M8 21h8a2 2 0 002-2V5a2 2 0 00-2-2H8a2 2 0 00-2 2v14a2 2 0 002 2z"/>
        </svg>
        <span class="text-[10px] font-semibold tracking-tight">Devices</span>
      </button>

      <button class="flex flex-col items-center gap-1 text-slate-500 hover:text-slate-300 transition-colors focus:outline-none">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/>
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
        </svg>
        <span class="text-[10px] font-semibold tracking-tight">Settings</span>
      </button>
    </div>
  </nav>

</body>
</html>