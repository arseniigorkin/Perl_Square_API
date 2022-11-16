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

=head2 Location ID
Set it up in the settings: no your Dashboard select in tht left menu "Settings" -> "Account & Settings"
Then expand in the left menu "Business" and click "Locations".
Manage your locations here.
Once the location is created successfully you have to grab its ID. To do that:
open the link: https://developer.squareup.com/apps
Click on the big "+" ander Applications;
come up with a name (any convenient for you);
click on the newly baked app with the name you entered previously,
in the left menu click on Locations and copy the desired location's ID.

!!! IMPORTANT: you can switch between two modes (test "Sandbox" and a "Production").
IDs and API keys will differ from each other. To switch between the modes just click on the
required one at the TOP of the page.
!!! Please, CHECK EVERY TIME the type of mode you use data from!
Also, check the host settings below for the right mode!
=cut
my $location_id = "<LOCATION_ID FOR THE SANDBOX>"; # for a sandbox
# my $location_id = "<LOCATION_ID FOR THE PRODUCTION>"; # for a production

# The URI for the API. Do not change unless you know what you do.
my $host = "https://connect.squareupsandbox.com/v2/locations/$location_id/checkouts"; # for Sandbox mode
#my $host = "https://connect.squareup.com/v2/locations/$location_id/checkouts"; # for a Production mode

=head2 Redirect URI
The URL below points to the page that will be shown after the payment completed/rejected.
This page must be a script (this one is I wrote for you: webhook.cgi)
that will handle the HTTP request from the query and, according the the data in the query,
check the status of the transaction, requesting from the Square server.
Based on the further response from the Square the script will show a related output to the user:
for a completed payment some "thank you" message, and for a rejected/cancelled - "sorry..."
For more information, please, check the webhook.cgi documentation -
comments in the script I wrote for you.
=cut

my $redirect_url = "https://example.com/cgi-bin/square/webhook.cgi"; # full page address when a payment is SUCCESSFUL

# a filename for storing vital payment data. You will need to use RDBS instead.
my $new_payment_file = "sent_payment_data.csv";

=head2 Query
	Reading the query from the "Buy Now" link on your online store.
	It accepts:
		user_id = TEXT (mandatory),
		price = INT (in cents, but not less than 50 cents) (mandatory),
		prod_name = TEXT (optional) - product name,
		prod_descr = TEXT (optional) - product description
		Here is a link example:
		<a href="https://example.com/cgi-bin/square_post.cgi?user_id=testUserId_015883&price=7050&prod_name=Test Product name&prod_descr=Descriptiont for this product" title="Link example">Test Product name</a>
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
	if (!$QUERY_hash{'price'} || $QUERY_hash{'price'} =~/\D/g) {
		die "Please, check the query. It does not meet minimum demands (no/incorrect price field)"
	}
	elsif (!$QUERY_hash{'user_id'} || $QUERY_hash{'user_id'} =~/\W/g) {
		die "Please, check the query. It does not meet minimum demands (no/incorrect user_id field)"
	}
	
} # if $ENV{'QUERY_STRING'}

else {
	die "Pardon, no parameters have been given..";
}

# Creating an LWP object and setting it up
my $ua = LWP::UserAgent->new();
$ua->agent('Mozilla/4.76 [en] (Win98; U)'); # can be changed if needed
$ua->default_header('Authorization',  "Bearer $SECRET_API_KEY");
$ua->default_header('Square-Version',  '2022-04-20'); # Square API ver. Do not change it, unless you know what you do
$ua->default_header('Content-type',  'application/json'); # Square API ver. Do not change it, unless you know what you do

# the constructor below represents the settings for a one product sale, "baked" on fly
my $json_HREF = {
	redirect_url => $redirect_url,
	idempotency_key => map({s/\=//g;
		$_} @{[ MIME::Base64::encode(time() . rand(999999999999) . rand(999999999999), '') ]}),
	order           => {
		idempotency_key => map({s/\=//g;
			$_} @{[ MIME::Base64::encode(time() . rand(999999999999) . rand(999999999999), '') ]}),
		order           => {
			location_id  => $location_id,
			line_items   => [
				{
					quantity     => "1", # a number of items of this type sold altogether
					base_price_money => {
						amount   => int $QUERY_hash{price}, # the product's price IN THE CENTS (5000 is for 50 USD),
						currency => "USD"
					},
					name     => $QUERY_hash{prod_name} || "Product purchase", # the current item's name
					note     => $QUERY_hash{prod_descr} || "No description", # the current item's description (optional)
				}
			],
			reference_id => $QUERY_hash{user_id}, # any pattern within regex \w class to identify the Customer on your side,
			state        => "OPEN" # do not change unless you know what you do
		}
	}
};
my $json_content = encode_json($json_HREF);

my $response = $ua->post($host, Content => $json_content);

if ($response->is_success) {
	
	# receiving and decoding JSON data from Square with the session information and storing it into a CSV file (you will use RDBS instead)
	my $json_response  = $response->decoded_content;
	my $href_json_response = decode_json($json_response);
	
	# testing the JSON data against Square legal structure
	if (
			defined $href_json_response->{checkout}->{redirect_url}
			&& $href_json_response->{checkout}->{redirect_url} eq $redirect_url
			&& defined $href_json_response->{checkout}->{id}
			&& $href_json_response->{checkout}->{id} =~/^[\w-]{20,}$/
			&& defined $href_json_response->{checkout}->{checkout_page_url}
			&& $href_json_response->{checkout}->{checkout_page_url} =~/^https:\/\/connect\.squareupsandbox\.com\/v2\/checkout\?c=(?:[\w\-\&=]+)$/ # for a sandboxing
			# && $href_json_response->{checkout}->{checkout_page_url} =~/^https:\/\/connect\.squareup\.com\/v2\/checkout\?c=(?:[\w\-\&=]+)$/ # for a production
			&& defined $href_json_response->{checkout}->{order}->{id}
			&& $href_json_response->{checkout}->{order}->{id} =~/^[\w]{20,}$/
			&& defined $href_json_response->{checkout}->{order}->{location_id}
			&& $href_json_response->{checkout}->{order}->{location_id} eq $location_id
			&& defined $href_json_response->{checkout}->{order}->{reference_id}
			&& $href_json_response->{checkout}->{order}->{reference_id} eq $QUERY_hash{user_id}
			&& defined $href_json_response->{checkout}->{order}->{line_items}->[0]->{name}
			&& $href_json_response->{checkout}->{order}->{line_items}->[0]->{name} eq $QUERY_hash{prod_name}
			&& defined $href_json_response->{checkout}->{order}->{line_items}->[0]->{total_money}->{amount}
			&& $href_json_response->{checkout}->{order}->{line_items}->[0]->{total_money}->{amount} == $QUERY_hash{price}
	) {
		
		open (STORAGE, "> $new_payment_file") or die "Could not manage to open the $new_payment_file for writing. Please, check the permissions.";
		
		# we store: [user_id], [amount], [SSID] and [order_id] to help you pick the right session from your RDBS on the payment completion.
		# DO NOT FORGET TO ALWAYS USE ONLY prepare() for SQL TEXT statements, as they can consist of unsafe symbols!
		print STORAGE <<CSV;
		user_id, $href_json_response->{checkout}->{order}->{reference_id}
		amount, $href_json_response->{checkout}->{order}->{line_items}->[0]->{total_money}->{amount}
		order_id, $href_json_response->{checkout}->{order}->{id}
		SSID, $href_json_response->{checkout}->{id}
CSV
		close STORAGE;
		
		# redirecting to the payment page at Squareup.com for this session
		print "Location: $href_json_response->{checkout}->{checkout_page_url}\n\n";
		exit;
		}
	
	else {
		# if the JSON form Square has invalid structure or data we show an error here
		print "Content-type: application/json\n\n";
		print '{"response": "ERROR"}';
	}
	
}
else {
	die 'Square returned an error: "'.$response->status_line."\"\n"; # can be replaced with a custom error page. The error can be stored in the log, if needed.
}
