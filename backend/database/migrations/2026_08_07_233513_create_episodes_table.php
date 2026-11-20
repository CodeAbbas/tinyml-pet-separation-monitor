<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('episodes', function (Blueprint $table) {
            $table->id();

            // Idempotency key: the gateway generates a UUID per episode, so a
            // replayed webhook updates this row instead of creating a duplicate.
            $table->uuid('event_id')->unique();

            $table->string('device_id')->default('nano33-01')->index();
            $table->timestamp('occurred_at')->index();

            // Headline anomaly score (weighted composite of the four z-scores).
            $table->float('composite_z');
            $table->unsignedSmallInteger('window_sec');

            // Discrete columns (not JSON) so the evaluation in Phase 7 can query,
            // chart and CSV-export individual features without unpacking blobs.
            $table->float('z_transition_rate');
            $table->float('z_dwell_entropy');
            $table->float('z_position_var');
            $table->float('z_activity');

            $table->float('f_transition_rate');
            $table->float('f_dwell_entropy');
            $table->float('f_position_var');
            $table->float('f_activity');

            // Full original payload retained for audit / reprocessing.
            $table->json('raw_payload')->nullable();

            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('episodes');
    }
};