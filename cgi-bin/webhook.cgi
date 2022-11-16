#!/usr/bin/perl
use strict;
use warnings FATAL => 'all';

use CGI::Carp qw/fatalsToBrowser/; # recommended to handle any errors, but can be removed if you prefer ro
use LWP::UserAgent;
use HTTP::Request::Common;
use JSON::XS;
use MIME::Base64;
# use Data::Dumper;

################## USER VARS SETUP
# Your actual API key (take one here, please: https://squareup.com/dashboard/apps/my-applications).
my $SECRET_API_KEY = '<YOUR SANDBOX SECRET KEY>'; # for sandbox
# my $SECRET_API_KEY = '<YOUR PRODUCTION SECRET KEY>'; # f a production

# The URI for the API. Do not change unless you know what you do.
my $host = "https://connect.squareupsandbox.com/v2/orders/"; # for Sandbox mode
#my $host = "https://connect.squareup.com/v2/orders/"; # for a Production mode

=head2 Query
	Reading the query from the Square response.
	It accepts:
		reference_id = TEXT (our user_id from the "Buy Now" link),
		transactionId = TEXT (order_id)
=cut

my %QUERY_hash;
if ($ENV{'QUERY_STRING'} && length ($ENV{'QUERY_STRING'}) > 0){
	
	my $buffer = $ENV{'QUERY_STRING'};
	my @_qPairs = split(/&/, $buffer);
	foreach (@_qPairs){
		my ($_key, $_value) = split(/=/, $_);
		$_value =~ s/%([a-fA-F0-9][a-fA-F0-9])/pack("C", hex($1))/eg;
		$QUERY_hash{$_key} = $_value;
	}
	if (!$QUERY_hash{'referenceId'} || $QUERY_hash{'referenceId'} =~/\W+/g) {
		die "Please, check the query. It does not meet minimum demands (no/incorrect reference_id field)"
	}
	elsif (!$QUERY_hash{'transactionId'} || $QUERY_hash{'transactionId'} =~/\W{10,}/g) {
		die "Please, check the query. It does not meet minimum demands (no/incorrect transactionId field)"
	}
	elsif (!$QUERY_hash{'checkoutId'} || $QUERY_hash{'checkoutId'} =~/\W{10,}/g) {
		die "Please, check the query. It does not meet minimum demands (no/incorrect checkoutId field)"
	}
	
	# adding the order_id to the query
	$host .= $QUERY_hash{'transactionId'};
	
} # if $ENV{'QUERY_STRING'}

else {
	die "Pardon, no parameters have been given.."; # make your own error response here
}

# Creating an LWP object and setting it up
my $ua = LWP::UserAgent->new();
$ua->agent('Mozilla/4.76 [en] (Win98; U)'); # can be changed if needed
$ua->default_header('Authorization',  "Bearer $SECRET_API_KEY");
$ua->default_header('Square-Version',  '2022-04-20'); # Square API ver. Do not change it, unless you know what you do
$ua->default_header('Content-type',  'application/json'); # Square API ver. Do not change it, unless you know what you do

# the constructor below sets the query for the GET order from Square
my $json_HREF = {
	reference_id => $QUERY_hash{referenceId},
	transactionId => $QUERY_hash{transactionId}
};
my $json_content = encode_json($json_HREF);

my $response = $ua->get($host, Content => $json_content);

if ($response->is_success) {
	
	# receiving and decoding JSON data from Square with the session information and storing it into a CSV file (you will use RDBS instead)
	my $json_response  = $response->decoded_content;
	my $href_json_response = decode_json($json_response);
	
	# testing the JSON data against Square legal structure
	if (
			defined $href_json_response->{order}->{id}
			&& $href_json_response->{order}->{id} =~/^[\w-]{20,}$/
			&& defined $href_json_response->{order}->{location_id}
			&& $href_json_response->{order}->{location_id} =~/^[\w]{10,}$/
			&& defined $href_json_response->{order}->{state}
			&& defined $href_json_response->{order}->{state} =~/^(COMPLETED|OPEN|CANCELED)$/
			&& defined $href_json_response->{order}->{reference_id}
			&& $href_json_response->{order}->{reference_id} =~/^\w+$/
			&& defined $href_json_response->{order}->{line_items}->[0]->{name}
			&& $href_json_response->{order}->{line_items}->[0]->{name} =~/[^ ]+/
			&& defined $href_json_response->{order}->{line_items}->[0]->{note}
			&& $href_json_response->{order}->{line_items}->[0]->{note} =~/[^ ]+/
			&& defined $href_json_response->{order}->{line_items}->[0]->{total_money}->{amount}
			&& $href_json_response->{order}->{line_items}->[0]->{total_money}->{amount} =~/^\d+$/
	) {

=head2 SQL
	Here you have to do next steps with your SQL:
	1. retrieve the session with the SSID from $QUERY_hash{'checkoutId'}
	2. match the information from your SQL (form this fetch)
	with the data in $href_json_response-{order}->... i.e.:
		a. {line_items}->[0]->{name},
		b. {line_items}->[0]->{total_money}->{amount}
		c. {reference_id} (it is your user_id)
	3. If the data is correct:
		3.1 check the $href_json_response->{order}->{state}.
		3.2 if it is "COMPLETED":
			3.2.1 UPDATE the actual SQL record with to give it a new status.
			3.2.2 Show "Thank you" page to the user.
		3.3 if it is "CANCELED":
			3.3.1 just show the "SORRY TO HEAR YOU HAVE CANCELED THE ORDER..." page
				and do NOTHING with the DB (or change a status cell (if you have) to "canceled"
				or just remove the whole record from the RDBS)
	4. If hte data is incorrect:
		4.1 show "Invalid data! Contact us about the issue at blablabla@example.com" page to the user.
	
	Please, do not forget to add print "Content-type: text/html\n\n"
	before any output to prevent error 500!
	
	DO NOT FORGET TO ALWAYS USE ONLY prepare() for SQL TEXT statements, as they can consist of unsafe symbols!
=cut
		
		# REMOVE TWO STRINGS BELOW (printing JSON). They just show you the response from the Square.
		print "Content-type: application/json\n\n";
		print $json_response;
	}
	
	else {
		
		die "Invalid data"; # Create your own error page. This is about the JSON data, obtained from the Square about the order has a wrong format/data
		
	}
	
}
else {
	
	die 'Square returned an error: "'.$response->status_line."\"\n"; # can be replaced with a custom error page. The error can be stored in the log, if needed.

}
